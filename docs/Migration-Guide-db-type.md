# Database 메타모델 확장 마이그레이션 가이드

## 개요

이 가이드는 Database 테이블에 `db_type` 컬럼을 추가하는 마이그레이션 과정을 설명합니다.

## 마이그레이션 내용

### 변경사항

- `databases` 테이블에 `db_type` 컬럼 추가
- 지원 데이터베이스 타입: `postgresql`, `mysql`, `sqlite`
- 기본값: `postgresql` (기존 레코드 호환성 보장)
- 성능 최적화를 위한 인덱스 추가

### 마이그레이션 파일

- 파일명: `alembic/versions/20250918_add_db_type_column.py`
- Revision ID: `20250918_add_db_type`

## 마이그레이션 실행 방법

### 1. 사전 준비

#### 데이터베이스 백업

```bash
# PostgreSQL 백업
pg_dump -h localhost -U backup_user -d backup_manager > backup_before_migration.sql

# 또는 Docker 환경에서
docker-compose exec postgres pg_dump -U backup_user backup_manager > backup_before_migration.sql
```

#### 애플리케이션 중지

```bash
# Docker Compose 환경
docker-compose stop app

# 또는 프로세스 직접 중지
pkill -f "uvicorn app.main:app"
```

### 2. 마이그레이션 실행

#### 로컬 환경

```bash
# 가상환경 활성화
source venv/bin/activate  # Linux/Mac
# 또는
venv\Scripts\activate  # Windows

# 마이그레이션 실행
alembic upgrade head

# 마이그레이션 상태 확인
alembic current
alembic history --verbose
```

#### Docker 환경

```bash
# 애플리케이션 컨테이너에서 마이그레이션 실행
docker-compose exec app alembic upgrade head

# 마이그레이션 상태 확인
docker-compose exec app alembic current
docker-compose exec app alembic history --verbose
```

### 3. 마이그레이션 검증

#### 스키마 확인

```sql
-- PostgreSQL에서 컬럼 확인
\d databases

-- 또는 SQL 쿼리로 확인
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'databases' AND column_name = 'db_type';

-- 인덱스 확인
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'databases' AND indexname LIKE '%db_type%';
```

#### 데이터 확인

```sql
-- 기존 레코드의 db_type 기본값 확인
SELECT id, name, db_type, environment
FROM databases
LIMIT 10;

-- db_type별 통계
SELECT db_type, COUNT(*) as count
FROM databases
GROUP BY db_type;
```

### 4. 애플리케이션 재시작

```bash
# Docker Compose 환경
docker-compose up -d app

# 로컬 환경
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 5. API 테스트

#### 새 데이터베이스 등록 테스트

```bash
# PostgreSQL 데이터베이스 등록
curl -X POST "http://localhost:8000/api/databases/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test_postgres",
    "display_name": "테스트 PostgreSQL",
    "host": "localhost",
    "port": 5432,
    "database_name": "testdb",
    "username": "testuser",
    "password": "testpass",
    "db_type": "postgresql",
    "environment": "development",
    "priority": "low"
  }'

# MySQL 데이터베이스 등록
curl -X POST "http://localhost:8000/api/databases/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test_mysql",
    "display_name": "테스트 MySQL",
    "host": "localhost",
    "port": 3306,
    "database_name": "testdb",
    "username": "testuser",
    "password": "testpass",
    "db_type": "mysql",
    "environment": "development",
    "priority": "low"
  }'
```

#### 필터링 테스트

```bash
# db_type별 필터링
curl "http://localhost:8000/api/databases/?db_type=postgresql"
curl "http://localhost:8000/api/databases/?db_type=mysql"

# 복합 필터링
curl "http://localhost:8000/api/databases/?db_type=postgresql&environment=production"
```

## 롤백 방법

### 마이그레이션 롤백

```bash
# 이전 리비전으로 롤백
alembic downgrade -1

# 또는 Docker 환경에서
docker-compose exec app alembic downgrade -1
```

### 수동 롤백 (긴급시)

```sql
-- 인덱스 제거
DROP INDEX IF EXISTS ix_databases_db_type_environment;
DROP INDEX IF EXISTS ix_databases_db_type;

-- 컬럼 제거
ALTER TABLE databases DROP COLUMN IF EXISTS db_type;
```

## 트러블슈팅

### 일반적인 문제

#### 1. 마이그레이션 실행 실패

```bash
# 오류 메시지 확인
alembic upgrade head --sql  # SQL만 출력하여 확인

# 강제 리비전 설정 (주의: 데이터 손실 가능)
alembic stamp head
```

#### 2. 기존 데이터와 충돌

```sql
-- NULL 값이 있는 경우 기본값 설정
UPDATE databases SET db_type = 'postgresql' WHERE db_type IS NULL;
```

#### 3. 인덱스 생성 실패

```sql
-- 수동으로 인덱스 생성
CREATE INDEX CONCURRENTLY ix_databases_db_type ON databases (db_type);
CREATE INDEX CONCURRENTLY ix_databases_db_type_environment ON databases (db_type, environment);
```

### 성능 고려사항

#### 대용량 테이블 처리

```sql
-- 인덱스를 CONCURRENTLY로 생성 (운영 환경)
CREATE INDEX CONCURRENTLY ix_databases_db_type ON databases (db_type);

-- 컬럼 추가 시 기본값 설정 후 제거
ALTER TABLE databases ADD COLUMN db_type VARCHAR(20) DEFAULT 'postgresql';
-- 데이터 확인 후
ALTER TABLE databases ALTER COLUMN db_type DROP DEFAULT;
```

## 검증 체크리스트

### 마이그레이션 후 확인사항

- [ ] `databases` 테이블에 `db_type` 컬럼이 추가되었는가?
- [ ] 기존 레코드의 `db_type`이 `postgresql`로 설정되었는가?
- [ ] 인덱스 `ix_databases_db_type`가 생성되었는가?
- [ ] 인덱스 `ix_databases_db_type_environment`가 생성되었는가?
- [ ] API에서 `db_type` 필터링이 작동하는가?
- [ ] 새 데이터베이스 등록 시 `db_type` 검증이 작동하는가?
- [ ] 잘못된 `db_type` 값에 대해 오류가 발생하는가?

### API 기능 확인사항

- [ ] `GET /api/databases/?db_type=postgresql` 작동
- [ ] `GET /api/databases/?db_type=mysql` 작동
- [ ] `GET /api/databases/?db_type=sqlite` 작동
- [ ] `POST /api/databases/` 에서 `db_type` 검증 작동
- [ ] `PUT /api/databases/{id}` 에서 `db_type` 수정 가능
- [ ] 정렬 기능에서 `sort=db_type` 작동

## 후속 작업

### DatabaseManager 어댑터화 준비

1. 각 DB 타입별 연결 어댑터 구현
2. 백업 엔진에서 DB 타입별 처리 로직 추가
3. 설정 검증에서 DB 타입별 필수 필드 검증

### 모니터링 설정

```sql
-- DB 타입별 통계 쿼리
SELECT
    db_type,
    environment,
    COUNT(*) as database_count,
    COUNT(CASE WHEN connection_status = 'connected' THEN 1 END) as connected_count
FROM databases
WHERE is_active = true
GROUP BY db_type, environment
ORDER BY db_type, environment;
```
