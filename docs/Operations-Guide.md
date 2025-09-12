# 운영 가이드

본 문서는 PostgreSQL WAL 아카이빙과 베이스/증분 백업, 시점복구(PITR) 운영 절차를 정리합니다.

## 1. 사전 준비

- PostgreSQL 클라이언트 도구 설치: `pg_dump`, `pg_basebackup` 가 PATH에서 실행 가능해야 함
- 서버 설정 접근 권한: `postgresql.conf`, `pg_hba.conf` 편집 권한
- 애플리케이션 설정: `config/settings.yaml`의 `backup.wal`/`backup.pitr` 값 점검
  - `backup.wal.archive_dir`: WAL 보관 경로
  - `backup.wal.keep_days`: WAL 보존 일수
  - `backup.pitr.enable`: PITR 사용 여부

## 2. PostgreSQL 서버 설정(WAL 아카이빙)

아래 설정은 서버의 `postgresql.conf`에 적용합니다(버전에 따라 유사 옵션 사용).

- wal_level = replica
- archive_mode = on
- archive_command = 'test ! -f "<ARCHIVE_DIR>/%f" && cp "%p" "<ARCHIVE_DIR>/%f"'
  - `<ARCHIVE_DIR>`는 `settings.yaml`의 `backup.wal.archive_dir`와 동일하게 맞춰주세요.
- max_wal_senders, wal_keep_size 등은 운영 정책에 맞게 설정

적용 후 서버 재시작이 필요할 수 있습니다.

## 3. 애플리케이션에서의 백업 실행

- 전체(베이스) 백업 실행

  - `POST /api/backups/database/{db_id}/base-backup`
  - 내부적으로 `pg_basebackup`을 실행하고 결과를 `tar.gz`(옵션 시 `.enc`)로 보관합니다.

- 증분 백업(WAL 스냅샷) 실행

  - `POST /api/backups/database/{db_id}/incremental-backup`
  - WAL 아카이브 디렉터리에서 기준 시각 이후 파일을 모아 `tar.gz`(옵션 시 `.enc`) 스냅샷을 생성합니다.

- WAL 유지보수(인덱싱/정리)
  - `POST /api/backups/wal/maintenance`
  - WAL 파일을 날짜별(YYYYMMDD)로 정리하고, `keep_days` 보존 정책에 따라 오래된 파일을 삭제합니다.

## 4. 보관 경로 구조 예시

- `backup.wal.archive_dir` 하위

  - `YYYYMMDD/0000000100000000000000A1` (WAL 파일)
  - `YYYYMMDD/0000000100000000000000A2`

- 베이스/증분 아티팩트
  - `data/backups/<database_name>/base_YYYYMMDD_HHMMSS_<backup_id>.tar.gz(.enc)`
  - `data/backups/<database_name>/wal_YYYYMMDD_HHMMSS_<backup_id>.tar.gz(.enc)`

## 5. 시점 복구(PITR) 개요

주의: PITR는 별도 복구 환경(테스트/스테이징)에서 검증 후 운영에 적용하세요.

1. 적합한 베이스 백업 선택

- 목표 시각 `T` 이전에 생성된 최신 베이스 백업 아카이브를 선택합니다.

2. 복구 환경 준비

- 복구 대상 디렉터리를 준비하고 베이스 백업 `tar.gz(.enc)`를 해제합니다.
- 암호화된 경우 `.enc`를 복호화(AES-256-GCM)하여 `tar.gz`로 복원한 뒤 압축을 해제합니다.

3. 필요한 WAL 범위 확보

- 목표 시각 `T`까지 적용 가능한 WAL 파일을 `archive_dir`에서 수집합니다.
- 운영 편의상 동일 날짜(및 인접 날짜)의 WAL을 모두 준비해 두는 것을 권장합니다.

4. recovery.signal 및 restore_command 설정

- 복구 디렉터리의 `postgresql.auto.conf` 또는 설정 파일에 아래를 구성합니다(버전별 방법 상이 가능).
  - `restore_command = 'cp "<ARCHIVE_DIR>/%f" "%p"'`
  - `recovery_target_time = 'YYYY-MM-DD HH:MM:SS+00'` (필요 시)
- 복구 디렉터리에 빈 파일 `recovery.signal` 생성

5. 인스턴스 기동 및 검증

- 해당 데이터 디렉터리로 PostgreSQL을 기동합니다.
- 로그에서 WAL 적용 진행 상황을 확인하고, 타겟 시각까지 복구되었는지 검증합니다.

## 6. 트러블슈팅 체크리스트

- **WAL 파일이 아카이브에 쌓이지 않음**

  - 서버 `archive_mode`, `archive_command` 재확인
  - `archive_command` 경로/권한 문제 점검

- **pg_basebackup 실패**

  - PATH에 `pg_basebackup` 존재 여부 확인
  - 연결 파라미터(host/port/user/password/ssl) 재확인
  - 대상 디스크 용량 부족 여부 점검

- **PITR 진행 시 WAL 누락**
  - 아카이브 경로와 날짜 폴더에 필요한 범위의 WAL 존재 여부 확인
  - 타임존/시각 표준(UTC vs 로컬) 혼동 주의

## 7. 보안/컴플라이언스 주의

- **암호화 키(ENCRYPTION_KEY)**는 32자이며, 운영 환경에서 안전하게 관리하세요.
- **저장소 암호화/권한**: 백업 파일이 저장되는 경로의 파일시스템 권한을 최소화하고, 필요 시 추가 암호화를 적용하세요.
- **전송 구간 보호**: 원격 전송이 있을 경우 SSH/SFTP 등 보안 채널을 사용하세요.

---

문의/개선 제안은 GitHub 이슈 `Phase 4: 고급 기능 및 최적화 / 4.1 증분 백업`에 남겨주세요.
