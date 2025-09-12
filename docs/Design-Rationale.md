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

## 2.2 설정 파일 시스템

- `ConfigManager`를 확장해 `${ENV}` 환경변수 재귀 확장, 간단 캐시 및 mtime 기반 변경 감지/리로드(`needs_reload`, `reload_databases_config`)를 지원합니다.
- `databases.yaml`에 대해 루트 `databases` 키와 각 항목의 필수 필드( name, host, port, database, username, password, environment, priority )를 검증하고 포트 타입을 확인합니다.
- API로 설정 조회/검증/리로드를 제공해 운영 중 안전한 동적 적용 기반을 마련했습니다: `GET /api/databases/config`, `POST /api/databases/config/validate`, `POST /api/databases/config/reload`.

## 3.1 대시보드 페이지

- Bootstrap 5 기반 반응형 레이아웃과 다크 테마 토글, 로딩 스피너를 적용해 사용자 경험을 개선하고, 최근 백업·활성 DB·상태 배지 등 핵심 위젯을 구성했습니다.
- Chart.js로 최근 7일 총/성공/실패 추이를 시각화하고, 일별 평균 소요 시간/압축률 보조차트를 추가해 백업 품질과 성능을 한 화면에서 파악할 수 있게 했습니다.
- 백엔드 모니터링 API와 연계(`GET /api/monitoring/status`, `GET /api/monitoring/dashboard`)하여 10초 간격 자동 갱신 및 실패 상세 링크(`/api/backups?status_filter=failed`) 제공으로 운영 가시성을 강화했습니다.

## 3.2 데이터베이스 관리 페이지

- 프론트엔드에 데이터베이스 목록/상태/액션 UI(`web/templates/databases.html`, `web/static/js/databases.js`)를 구성하고, 새로고침/추가/수정/삭제/연결 테스트 상호작용을 모달/버튼 기반으로 단순화했습니다.
- 백엔드는 기존 REST API(`/api/databases` CRUD, `POST /api/databases/{id}/test-connection`)에 맞춰 필요한 필드만 사용해 상호 운용성을 높이고, 소프트 삭제로 운영 안전성을 확보했습니다.
- 우선 검증·알림은 브라우저 기본(알림/확인)으로, 후속 고도화에서 토스트/유효성 강화/검색·정렬·페이징을 순차 추가 가능하도록 확장 포인트를 남겼습니다.
