# 설계 근거 요약

## 1.1 프로젝트 구조 설정 및 개발 환경 구축

- 모듈 경계가 명확한 디렉터리 구조(`app/`, `config/`, `docs/`, `web/`)로 유지보수성과 확장성을 확보했습니다.
- 의존성은 `requirements.txt`로 고정하고, 환경설정은 `.env` + `config/*.yaml`로 외부화하여 배포 환경별 차등 구성을 용이하게 했습니다.
- 향후 CI/CD와 Docker 적용을 고려해 표준 파이썬 프로젝트 레이아웃과 UTF-8 기본 환경(Windows 포함)을 채택했습니다.

## 1.2 FastAPI 서버 구현

- `app/main.py`에서 `FastAPI()` 인스턴스, CORS/TrustedHost/정적 파일을 설정해 보안과 운영 편의성을 균형 있게 확보했습니다.
- `app/api/*.py` 라우터 분리와 `lifespan` 초기화(`init_database`, 디렉터리 생성)로 시동 시 안정성과 기능적 응집도를 높였습니다.
- 문서화 경로(`/api/docs`, `/api/redoc`, `/api/openapi.json`)를 고정해 운영/디버깅 가시성을 강화했습니다.

## 1.3 PostgreSQL 메타데이터 DB 설계 및 구현

- `app/database.py`의 모델은 UUID 키, 시간 필드, 상태/지표 컬럼으로 백업 이력 추적에 필요한 최소 스키마를 반영했습니다.
- 조회 패턴 기반 인덱스와 `SystemLog.details`의 JSONB + GIN 인덱스를 적용해 운영 시 모니터링/탐색 비용을 절감했습니다.
- Alembic(`alembic.ini`, `alembic/env.py`)을 통해 `alembic upgrade head`로 자동 스키마 최신화를 보장하고, 타입 변경 시 `USING` 절로 이행 안정성을 확보했습니다.

## 1.4 기본 백업 엔진 구현 (pg_dump 기반)

- `app/core/backup_engine.py`의 `BackupEngine`으로 pg_dump 실행·압축(gzip)·암호화(AES-256-GCM)·체크섬까지 단일 플로우로 구성했습니다.
- `BackgroundTasks`로 API 요청과 비동기 실행을 분리해 사용자 응답성을 유지하고, 메타데이터(`file_path`,`checksum`,`duration_seconds` 등)를 즉시 기록합니다.
- `ENCRYPTION_KEY(32자)` 검증과 `pg_dump_version` 기록으로 보안/재현가능성을 높였으며, 추후 비밀번호 암호화 저장/복호화 연계를 전제로 설계했습니다.

## 2.1 DatabaseManager 구현

- `DatabaseManager`를 도입해 psycopg2 `SimpleConnectionPool` 기반 다중 DB 연결 풀을 관리하고, 최소/최대 커넥션·풀 획득/반납/종료 기능을 제공합니다.
- 실제 연결 테스트(`POST /api/databases/{id}/test-connection`)와 풀 제어/요약 API(`init-pool`, `close-pool`, `pool-status`)를 추가해 응답시간·성공/실패를 기록하고 `connection_status`/`last_connection_test`를 갱신합니다.
- 애플리케이션 종료 시 `lifespan`에서 `close_all()`로 자원 누수를 방지하고, `GET /api/monitoring/db-status`로 전 DB의 연결 상태를 모니터링합니다.
