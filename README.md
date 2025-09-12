# 클라우드 데이터베이스 자동 백업 시스템

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-13+-blue.svg)](https://postgresql.org)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/Hobby2025/LocalBackUpManager)

## 개요

클라우드 데이터베이스를 로컬 하드디스크에 주기적으로 자동 백업하는 엔터프라이즈급 백업 솔루션입니다.
다중 데이터베이스 환경에서의 통합 백업 관리와 웹 기반 관리 인터페이스를 제공합니다.

### 주요 목적

- 클라우드 데이터베이스의 안전한 로컬 백업
- 데이터 손실 위험 최소화 및 재해 복구 대비
- 백업 과정의 완전 자동화를 통한 운영 효율성 향상
- 다중 데이터베이스 환경에서의 통합 백업 관리

## 핵심 기능

- 🗄️ **다중 데이터베이스 지원**: 여러 인스턴스 동시 관리
- ⏰ **스케줄링된 자동 백업**: 우선순위 기반 스케줄링
- 📈 **증분 백업 및 전체 백업**: WAL 기반 PITR 지원
- 🔒 **백업 파일 압축 및 암호화**: AES-256 암호화
- 🌐 **웹 기반 관리 인터페이스**: 직관적인 대시보드
- 📊 **실시간 모니터링 및 알림**: 계층적 알림 시스템
- 📅 **백업 파일 보존 정책**: 환경별 차등 정책
- 📝 **로그 및 에러 추적**: 상세한 감사 로그

## 기술 스택

### 백엔드

- **Python 3.8+**: 메인 개발 언어
- **FastAPI 0.104+**: REST API 서버
- **PostgreSQL 13+**: 메타데이터 저장
- **APScheduler 3.10+**: 백업 작업 스케줄링
- **SQLAlchemy 2.0+**: ORM
- **Alembic**: 데이터베이스 마이그레이션

### 프론트엔드

- **Bootstrap 5**: 반응형 웹 인터페이스
- **Chart.js**: 백업 통계 시각화
- **FullCalendar**: 백업 스케줄 관리
- **SweetAlert2**: 사용자 알림

### 보안 & 도구

- **Cryptography**: AES-256 암호화
- **PostgreSQL 도구**: pg_dump, pg_restore, pg_basebackup
- **압축**: gzip, lz4, zstd
- **알림**: SMTP, Slack API, Discord Webhook

## 프로젝트 구조

```
LocalBackUpManager/
├── app/                    # 애플리케이션 코드
│   ├── api/               # API 라우터
│   │   ├── databases.py   # 데이터베이스 관리 API
│   │   ├── backups.py     # 백업 관리 API
│   │   ├── schedules.py   # 스케줄 관리 API
│   │   └── monitoring.py  # 모니터링 API
│   ├── core/              # 핵심 비즈니스 로직
│   │   ├── backup_engine.py    # 백업 엔진
│   │   ├── database_manager.py # DB 매니저
│   │   ├── scheduler.py        # 스케줄러
│   │   ├── encryption.py       # 암호화
│   │   ├── compression.py      # 압축
│   │   └── notification.py     # 알림
│   ├── models/            # SQLAlchemy 모델
│   ├── schemas/           # Pydantic 스키마
│   └── utils/             # 유틸리티 함수
├── web/                   # 웹 인터페이스
│   ├── static/           # 정적 파일 (CSS, JS, 이미지)
│   └── templates/        # HTML 템플릿
├── data/                  # 데이터 저장소
│   ├── backups/          # 백업 파일
│   ├── logs/             # 로그 파일
│   └── postgresql_metadata/ # 메타데이터 DB
├── config/                # 설정 파일
│   ├── settings.yaml     # 애플리케이션 설정
│   └── databases.yaml    # 데이터베이스 설정
├── docs/                  # 문서
│   ├── Proposal-Project.md      # 프로젝트 기획서
│   ├── Development-Guidelines.md # 개발 지침서
│   ├── PostgreSQL-Schema.md     # DB 스키마 설계
│   └── GitHub-Issues-Guidelines.md # 이슈 관리 가이드
├── tests/                 # 테스트 코드
├── requirements.txt       # Python 의존성
├── docker-compose.yml     # Docker 구성
├── Dockerfile            # Docker 이미지
└── README.md             # 프로젝트 설명서
```

## 빠른 시작

### 시스템 요구사항

**최소 요구사항:**

- OS: Linux/Windows/macOS
- Python: 3.8+
- RAM: 2GB
- Storage: 10GB (시스템) + 백업 용량
- Network: 안정적인 인터넷 연결

**권장 요구사항:**

- OS: Ubuntu 20.04 LTS / CentOS 8
- Python: 3.11+
- RAM: 8GB
- Storage: SSD 50GB + 백업 전용 스토리지
- Network: 1Gbps 이상

### 설치 방법

#### 1. 저장소 클론

```bash
git clone https://github.com/your-org/LocalBackUpManager.git
cd LocalBackUpManager
```

#### 2. 가상환경 생성 및 활성화

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows
```

#### 3. 의존성 설치

```bash
pip install -r requirements.txt
```

#### 4. 환경 설정

```bash
cp config/settings.yaml.example config/settings.yaml
cp config/databases.yaml.example config/databases.yaml
cp .env.example .env
```

#### 5. 환경변수 설정

```bash
# .env 파일 편집
METADATA_DB_PASSWORD=your_secure_password
ENCRYPTION_KEY=your_32_character_encryption_key
SMTP_USERNAME=your_email@company.com
SMTP_PASSWORD=your_app_password
```

#### 6. 메타데이터 데이터베이스 초기화

```bash
# PostgreSQL 메타데이터 DB 생성
createdb backup_metadata

# 마이그레이션 실행
alembic upgrade head
```

#### 7. 설정 검증

```bash
python -m app.main validate-config
```

#### 8. 서비스 시작

```bash
python -m app.main
```

웹 인터페이스: http://localhost:8000

### Docker로 실행

```bash
# Docker Compose로 실행
docker-compose up -d

# 개별 컨테이너 빌드
docker build -t backup-manager .
docker run -p 8000:8000 backup-manager
```

## 📖 사용법

### 1. 데이터베이스 추가

1. 웹 인터페이스에서 "데이터베이스 관리" 페이지로 이동
2. "새 데이터베이스 추가" 버튼 클릭
3. 연결 정보 입력 (호스트, 포트, 사용자명, 비밀번호)
4. 환경 및 우선순위 설정
5. 연결 테스트 후 저장

### 2. 백업 스케줄 설정

1. "스케줄 관리" 페이지에서 백업 일정 설정
2. 전체 백업 및 증분 백업 스케줄 구성
3. 압축 및 암호화 옵션 선택
4. 보존 정책 설정

### 3. 수동 백업 실행

1. "백업 관리" 페이지에서 대상 데이터베이스 선택
2. "백업 실행" 버튼 클릭
3. 백업 유형 선택 (전체/증분/스키마/데이터)
4. 실행 및 진행 상황 모니터링

### 4. 모니터링 및 알림

1. 대시보드에서 실시간 백업 상태 확인
2. 백업 성공률 및 성능 메트릭 모니터링
3. 알림 설정으로 이메일/Slack/Discord 알림 구성

## 🔧 설정

### 데이터베이스 설정 (config/databases.yaml)

```yaml
databases:
  production_db:
    name: "운영 데이터베이스"
    host: "prod-db.company.com"
    port: 5432
    database: "production"
    username: "backup_user"
    password: "${PROD_DB_PASSWORD}"
    environment: "production"
    priority: "high"

    backup_config:
      full_backup_schedule: "0 2 * * 0" # 매주 일요일 2시
      incremental_schedule: "0 */6 * * *" # 6시간마다
      compression: "lz4"
      encryption: true
      retention_policy:
        daily: 7
        weekly: 4
        monthly: 12
```

### 알림 설정 (config/settings.yaml)

```yaml
notifications:
  email:
    enabled: true
    smtp_server: "smtp.gmail.com"
    smtp_port: 587
    use_tls: true
  slack:
    enabled: true
    webhook_url: "${SLACK_WEBHOOK_URL}"
  discord:
    enabled: false
    webhook_url: "${DISCORD_WEBHOOK_URL}"
```

## API 문서

서버 실행 후 다음 URL에서 자동 생성된 API 문서를 확인할 수 있습니다:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 주요 API 엔드포인트

```
GET    /api/databases              # 모든 데이터베이스 목록 조회
POST   /api/databases              # 새 데이터베이스 추가
GET    /api/backups                # 모든 백업 목록 조회
POST   /api/backups/database/{db_id} # 특정 DB 백업 실행
GET    /api/schedules              # 모든 스케줄 조회
POST   /api/schedules/database/{db_id} # 새 스케줄 생성
GET    /api/monitoring/status      # 시스템 상태 조회
```

## 테스트

```bash
# 단위 테스트 실행
pytest tests/unit/

# 통합 테스트 실행
pytest tests/integration/

# 커버리지 리포트
pytest --cov=app tests/

# 특정 테스트 실행
pytest tests/test_backup_engine.py -v
```

## 모니터링

### 주요 메트릭

- 백업 성공률
- 백업 소요 시간
- 백업 파일 크기
- 디스크 사용량
- 데이터베이스 연결 상태

### 알림 레벨

- **CRITICAL**: 운영 DB 백업 실패, 시스템 오류
- **WARNING**: 디스크 공간 부족, 성능 저하
- **INFO**: 백업 완료, 정기 리포트

## 보안

### 데이터 보안

- 백업 파일 AES-256 암호화
- 데이터베이스 연결 정보 암호화 저장
- SSL/TLS 연결 사용

### 접근 제어

- 백업 디렉토리 권한 제한 (700)
- 설정 파일 권한 제한 (600)
- 환경변수를 통한 민감 정보 관리

## 배포

### Docker 배포

```bash
# 프로덕션 환경 배포
docker-compose -f docker-compose.prod.yml up -d

# 스케일링
docker-compose up --scale backup-manager=3
```

### 시스템 서비스 등록

```bash
# systemd 서비스 등록 (Linux)
sudo cp scripts/backup-manager.service /etc/systemd/system/
sudo systemctl enable backup-manager
sudo systemctl start backup-manager
```

## 문서

- [프로젝트 기획서](docs/Proposal-Project.md)
- [개발 지침서](docs/Development-Guidelines.md)
- [PostgreSQL 스키마 설계](docs/PostgreSQL-Schema.md)
- [GitHub 이슈 관리 가이드](docs/Issues-Guidelines.md)

## 기여하기

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

자세한 기여 가이드라인은 [개발 지침서](docs/Development-Guidelines.md)를 참고하세요.

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참고하세요.

## 지원

- 이슈 리포트: [GitHub Issues](https://github.com/your-org/LocalBackUpManager/issues)
- 문서: [프로젝트 문서](docs/)

## 로드맵

### Phase 1: 핵심 인프라 구축

- 1.1 프로젝트 구조 설정 및 개발 환경 구축

  - [x] 디렉토리 구조 생성
  - [x] requirements.txt 작성
  - [x] 기본 설정 파일 구조 설계
  - [x] 개발 환경 설정 문서 작성

- 1.2 FastAPI 기반 REST API 서버 구현

  - [x] FastAPI 애플리케이션 초기 설정
  - [x] 기본 라우터 구조 설계
  - [x] CORS 및 미들웨어 설정
  - [x] 기본 엔드포인트 구현

- 1.3 PostgreSQL 메타데이터 데이터베이스 설계 및 구현

  - [x] PostgreSQL 데이터베이스 스키마 설계
  - [x] SQLAlchemy 모델 정의 (UUID, JSONB 활용)
  - [x] Alembic 마이그레이션 시스템 구축
  - [x] 데이터베이스 초기화 스크립트 작성
  - [x] 트리거 및 뷰 생성
  - [x] 인덱스 최적화 적용

- 1.4 기본 백업 엔진 구현 (pg_dump 기반)

  - [x] BackupEngine 클래스 기본 구조
  - [x] pg_dump 실행 로직 구현
  - [x] 백업 파일 압축 기능
  - [x] 기본 암호화 기능
  - [x] 백업 메타데이터 저장

### Phase 2: 다중 데이터베이스 지원

- 2.1 DatabaseManager 구현

  - [x] 다중 DB 연결 관리
  - [x] 연결 풀 관리
  - [x] DB 상태 모니터링
  - [x] 연결 테스트 기능

- 2.2 설정 파일 시스템
  - [ ] YAML 설정 파일 구조 설계
  - [ ] 환경변수 기반 보안 설정
  - [ ] 설정 검증 로직
  - [ ] 동적 설정 로드

### Phase 3: 웹 인터페이스 개발

- 3.1 대시보드 페이지

  - [ ] 반응형 대시보드 레이아웃
  - [ ] 실시간 상태 모니터링 위젯
  - [ ] Chart.js 기반 통계 차트
  - [ ] 시스템 상태 표시

- 3.2 데이터베이스 관리 페이지
  - [ ] DB 목록 및 상태 표시
  - [ ] DB 추가/수정/삭제 폼
  - [ ] 연결 테스트 기능
  - [ ] DB별 설정 관리

### Phase 4: 고급 기능 및 최적화

- 4.1 증분 백업 구현

  - [ ] WAL 아카이빙 설정
  - [ ] 증분 백업 로직 구현
  - [ ] PITR 지원 기능
  - [ ] 백업 체인 관리

- 4.2 성능 최적화
  - [ ] LZ4, ZSTD 압축 알고리즘 추가
  - [ ] 병렬 백업 처리 최적화
  - [ ] 메모리 사용량 최적화
  - [ ] 성능 벤치마크 테스트

### Phase 5: 알림 및 모니터링 시스템

- 5.1 알림 시스템 구현

  - [ ] Email 알림 구현
  - [ ] Slack 웹훅 연동
  - [ ] Discord 웹훅 연동
  - [ ] 계층적 알림 정책

- 5.2 모니터링 대시보드
  - [ ] 실시간 백업 상태 모니터링
  - [ ] 성능 메트릭 수집
  - [ ] 자동 리포트 생성
  - [ ] 알림 이력 관리

### Phase 6: 보안 및 컴플라이언스

- 6.1 보안 강화

  - [ ] AES-256 암호화 강화
  - [ ] 암호화 키 관리 시스템
  - [ ] 접근 권한 관리
  - [ ] SSL/TLS 연결 강제

- 6.2 감사 시스템
  - [ ] 상세 감사 로그 시스템
  - [ ] 접근 기록 추적
  - [ ] 규정 준수 리포트
  - [ ] 보안 정책 자동 적용

### Phase 7: 테스트 및 배포 준비

- 7.1 테스트 시스템

  - [ ] 단위 테스트 작성 (90% 커버리지)
  - [ ] 통합 테스트 구현
  - [ ] 성능/부하 테스트(덤프 시간/파일 크기/압축률)
  - [ ] 회귀 테스트(기존 PostgreSQL 기능 영향 검증)
  - [ ] 운영/로컬 환경별 실행 가이드 점검

- 7.2 배포 시스템
  - [ ] Dockerfile 작성
  - [ ] docker-compose.yml 구성
  - [ ] CI/CD 파이프라인 구축
  - [ ] 운영 문서 작성

### Phase 8: DB Type 확장 및 안정화

- 8.1 메타모델 확장 및 마이그레이션 (db_type 추가)

  - [ ] Database 테이블에 db_type 컬럼 추가 (postgresql/mysql/sqlite)
  - [ ] Alembic 마이그레이션 생성 및 적용 가이드
  - [ ] API 입력 검증에 db_type 반영 (생성/수정)
  - [ ] config/databases.yaml 예시 업데이트 (DB 유형별 샘플)

- 8.2 DatabaseManager 어댑터화 (연결/풀/테스트)

  - [ ] DatabaseAdapter 인터페이스 정의(create_pool/getconn/putconn/close_all/test_connection)
  - [ ] PostgresAdapter 구현(기존 psycopg2 기반 이식)
  - [ ] MySQLAdapter 구현(PyMySQL 또는 mysqlclient 기반, 풀 전략 결정)
  - [ ] SQLiteAdapter 구현(sqlite3, 풀 불필요 처리)
  - [ ] /api/databases/\* 엔드포인트가 어댑터 기반으로 동작하도록 변경

- 8.3 BackupEngine 백업 전략 어댑터

  - [ ] BackupAdapter 인터페이스 정의(run_backup, 옵션 구성)
  - [ ] PostgresBackupAdapter(pg_dump) 유지/정리
  - [ ] MySQLBackupAdapter(mysqldump, 인증/옵션/에러 처리)
  - [ ] SQLiteBackupAdapter(일관성 있는 파일 스냅샷/backup API)
  - [ ] 공통 후처리 재사용(압축/암호화/체크섬/메타데이터)

- 8.4 설정·문서·배포 업데이트

  - [ ] README/Development-Guidelines에 다중 DB 지원 가이드 추가
  - [ ] databases.yaml에 mysql/sqlite 예시 추가 및 주석 강화
  - [ ] requirements.txt에 MySQL 드라이버 추가(PyMySQL 또는 mysqlclient) 검토
  - [ ] Dockerfile에 mysql-client(mysqldump) 설치 추가

- 8.5 통합 및 안정화 테스트

  - [ ] DB 유형별 연결 테스트/E2E 백업 시나리오 케이스 작성
  - [ ] 성능/부하 테스트(덤프 시간/파일 크기/압축률)
  - [ ] 회귀 테스트(기존 PostgreSQL 기능 영향 검증)
  - [ ] 운영/로컬 환경별 실행 가이드 점검
