# PostgreSQL 메타데이터 데이터베이스 스키마 설계

## 📋 개요

백업 시스템의 메타데이터를 관리하기 위한 PostgreSQL 데이터베이스 스키마 설계서입니다.

## 🗄️ 데이터베이스 설정

### 연결 정보

```yaml
# config/metadata_db.yaml
metadata_database:
  host: "localhost"
  port: 5432
  database: "backup_metadata"
  username: "backup_admin"
  password: "${METADATA_DB_PASSWORD}"
  ssl_mode: "require"
  pool_size: 10
  max_overflow: 20
```

### 환경변수

```bash
# .env
METADATA_DB_PASSWORD=your_secure_password
METADATA_DB_URL=postgresql://backup_admin:password@localhost:5432/backup_metadata
```

## 📊 테이블 스키마

### 1. databases (데이터베이스 정보)

```sql
CREATE TABLE databases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    host VARCHAR(255) NOT NULL,
    port INTEGER NOT NULL DEFAULT 5432,
    database_name VARCHAR(255) NOT NULL,
    username VARCHAR(255) NOT NULL,
    password_encrypted TEXT NOT NULL,
    ssl_mode VARCHAR(20) DEFAULT 'require',
    environment VARCHAR(20) NOT NULL CHECK (environment IN ('production', 'staging', 'development')),
    priority VARCHAR(10) NOT NULL CHECK (priority IN ('high', 'medium', 'low')),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_connection_test TIMESTAMP WITH TIME ZONE,
    connection_status VARCHAR(20) DEFAULT 'unknown' CHECK (connection_status IN ('connected', 'disconnected', 'error', 'unknown'))
);

-- 인덱스
CREATE INDEX idx_databases_environment ON databases(environment);
CREATE INDEX idx_databases_priority ON databases(priority);
CREATE INDEX idx_databases_is_active ON databases(is_active);
CREATE UNIQUE INDEX idx_databases_name ON databases(name);
```

### 2. backup_configs (백업 설정)

```sql
CREATE TABLE backup_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    database_id UUID NOT NULL REFERENCES databases(id) ON DELETE CASCADE,
    full_backup_schedule VARCHAR(100), -- cron 표현식
    incremental_schedule VARCHAR(100), -- cron 표현식
    compression_algorithm VARCHAR(20) DEFAULT 'gzip' CHECK (compression_algorithm IN ('gzip', 'lz4', 'zstd')),
    encryption_enabled BOOLEAN DEFAULT true,
    retention_daily INTEGER DEFAULT 7,
    retention_weekly INTEGER DEFAULT 4,
    retention_monthly INTEGER DEFAULT 12,
    backup_timeout INTEGER DEFAULT 3600, -- 초 단위
    max_parallel_jobs INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스
CREATE UNIQUE INDEX idx_backup_configs_database ON backup_configs(database_id);
```

### 3. backups (백업 실행 이력)

```sql
CREATE TABLE backups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    database_id UUID NOT NULL REFERENCES databases(id) ON DELETE CASCADE,
    backup_type VARCHAR(20) NOT NULL CHECK (backup_type IN ('full', 'incremental', 'pitr', 'schema', 'data')),
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    file_path TEXT,
    file_size BIGINT, -- 바이트 단위
    compressed_size BIGINT, -- 바이트 단위
    compression_ratio DECIMAL(5,2),
    is_encrypted BOOLEAN DEFAULT false,
    checksum VARCHAR(64), -- SHA-256 해시
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    error_message TEXT,
    pg_dump_version VARCHAR(20),
    database_size BIGINT, -- 백업 시점의 DB 크기
    wal_start_lsn VARCHAR(20), -- WAL 시작 LSN (증분 백업용)
    wal_end_lsn VARCHAR(20), -- WAL 종료 LSN (증분 백업용)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스
CREATE INDEX idx_backups_database_id ON backups(database_id);
CREATE INDEX idx_backups_status ON backups(status);
CREATE INDEX idx_backups_backup_type ON backups(backup_type);
CREATE INDEX idx_backups_started_at ON backups(started_at);
CREATE INDEX idx_backups_completed_at ON backups(completed_at);
```

### 4. schedules (스케줄 정보)

```sql
CREATE TABLE schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    database_id UUID NOT NULL REFERENCES databases(id) ON DELETE CASCADE,
    schedule_type VARCHAR(20) NOT NULL CHECK (schedule_type IN ('full', 'incremental')),
    cron_expression VARCHAR(100) NOT NULL,
    timezone VARCHAR(50) DEFAULT 'UTC',
    is_active BOOLEAN DEFAULT true,
    next_run TIMESTAMP WITH TIME ZONE,
    last_run TIMESTAMP WITH TIME ZONE,
    run_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스
CREATE INDEX idx_schedules_database_id ON schedules(database_id);
CREATE INDEX idx_schedules_is_active ON schedules(is_active);
CREATE INDEX idx_schedules_next_run ON schedules(next_run);
```

### 5. notifications (알림 이력)

```sql
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    database_id UUID REFERENCES databases(id) ON DELETE SET NULL,
    backup_id UUID REFERENCES backups(id) ON DELETE SET NULL,
    notification_type VARCHAR(20) NOT NULL CHECK (notification_type IN ('email', 'slack', 'discord', 'webhook')),
    level VARCHAR(10) NOT NULL CHECK (level IN ('info', 'warning', 'critical')),
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    recipient VARCHAR(255),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed')),
    sent_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스
CREATE INDEX idx_notifications_database_id ON notifications(database_id);
CREATE INDEX idx_notifications_backup_id ON notifications(backup_id);
CREATE INDEX idx_notifications_level ON notifications(level);
CREATE INDEX idx_notifications_status ON notifications(status);
CREATE INDEX idx_notifications_created_at ON notifications(created_at);
```

### 6. system_logs (시스템 로그)

```sql
CREATE TABLE system_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    level VARCHAR(10) NOT NULL CHECK (level IN ('debug', 'info', 'warning', 'error', 'critical')),
    component VARCHAR(50) NOT NULL, -- backup_engine, scheduler, api, etc.
    message TEXT NOT NULL,
    details JSONB,
    database_id UUID REFERENCES databases(id) ON DELETE SET NULL,
    backup_id UUID REFERENCES backups(id) ON DELETE SET NULL,
    user_id VARCHAR(100), -- 향후 사용자 관리용
    ip_address INET,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스
CREATE INDEX idx_system_logs_level ON system_logs(level);
CREATE INDEX idx_system_logs_component ON system_logs(component);
CREATE INDEX idx_system_logs_database_id ON system_logs(database_id);
CREATE INDEX idx_system_logs_created_at ON system_logs(created_at);
CREATE INDEX idx_system_logs_details ON system_logs USING GIN(details);
```

### 7. backup_statistics (백업 통계)

```sql
CREATE TABLE backup_statistics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    database_id UUID NOT NULL REFERENCES databases(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    total_backups INTEGER DEFAULT 0,
    successful_backups INTEGER DEFAULT 0,
    failed_backups INTEGER DEFAULT 0,
    total_size BIGINT DEFAULT 0, -- 바이트 단위
    avg_duration DECIMAL(10,2), -- 초 단위
    min_duration INTEGER,
    max_duration INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스
CREATE UNIQUE INDEX idx_backup_statistics_db_date ON backup_statistics(database_id, date);
CREATE INDEX idx_backup_statistics_date ON backup_statistics(date);
```

## 🔧 초기 데이터 및 함수

### 트리거 함수 (updated_at 자동 업데이트)

```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 트리거 생성
CREATE TRIGGER update_databases_updated_at BEFORE UPDATE ON databases
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_backup_configs_updated_at BEFORE UPDATE ON backup_configs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_backups_updated_at BEFORE UPDATE ON backups
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_schedules_updated_at BEFORE UPDATE ON schedules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_backup_statistics_updated_at BEFORE UPDATE ON backup_statistics
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

### 뷰 (자주 사용되는 쿼리)

```sql
-- 데이터베이스별 최신 백업 상태
CREATE VIEW v_latest_backup_status AS
SELECT
    d.id as database_id,
    d.name,
    d.display_name,
    d.environment,
    d.priority,
    d.connection_status,
    b.backup_type,
    b.status as backup_status,
    b.completed_at as last_backup_time,
    b.file_size,
    b.duration_seconds,
    CASE
        WHEN b.completed_at > CURRENT_TIMESTAMP - INTERVAL '24 hours' THEN 'recent'
        WHEN b.completed_at > CURRENT_TIMESTAMP - INTERVAL '7 days' THEN 'normal'
        ELSE 'outdated'
    END as backup_freshness
FROM databases d
LEFT JOIN LATERAL (
    SELECT * FROM backups
    WHERE database_id = d.id
    AND status = 'completed'
    ORDER BY completed_at DESC
    LIMIT 1
) b ON true
WHERE d.is_active = true;

-- 백업 성공률 통계
CREATE VIEW v_backup_success_rate AS
SELECT
    d.id as database_id,
    d.name,
    d.environment,
    COUNT(b.id) as total_backups,
    COUNT(CASE WHEN b.status = 'completed' THEN 1 END) as successful_backups,
    COUNT(CASE WHEN b.status = 'failed' THEN 1 END) as failed_backups,
    ROUND(
        COUNT(CASE WHEN b.status = 'completed' THEN 1 END) * 100.0 /
        NULLIF(COUNT(b.id), 0), 2
    ) as success_rate
FROM databases d
LEFT JOIN backups b ON d.id = b.database_id
WHERE d.is_active = true
AND b.created_at > CURRENT_TIMESTAMP - INTERVAL '30 days'
GROUP BY d.id, d.name, d.environment;
```

## 🛠️ SQLAlchemy 모델 예시

```python
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, BigInteger, Decimal, Date
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import uuid

Base = declarative_base()

class Database(Base):
    __tablename__ = 'databases'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    display_name = Column(String(255), nullable=False)
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False, default=5432)
    database_name = Column(String(255), nullable=False)
    username = Column(String(255), nullable=False)
    password_encrypted = Column(Text, nullable=False)
    ssl_mode = Column(String(20), default='require')
    environment = Column(String(20), nullable=False)
    priority = Column(String(10), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_connection_test = Column(DateTime(timezone=True))
    connection_status = Column(String(20), default='unknown')

class Backup(Base):
    __tablename__ = 'backups'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    database_id = Column(UUID(as_uuid=True), nullable=False)
    backup_type = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False)
    file_path = Column(Text)
    file_size = Column(BigInteger)
    compressed_size = Column(BigInteger)
    compression_ratio = Column(Decimal(5,2))
    is_encrypted = Column(Boolean, default=False)
    checksum = Column(String(64))
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    duration_seconds = Column(Integer)
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

## 🔄 마이그레이션 관리

### Alembic 설정

```python
# alembic/env.py
from alembic import context
from sqlalchemy import engine_from_config, pool
from app.models import Base

target_metadata = Base.metadata

def run_migrations_online():
    connectable = engine_from_config(
        context.config.get_section(context.config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()
```

### 초기 마이그레이션 생성

```bash
# 마이그레이션 초기화
alembic init alembic

# 첫 번째 마이그레이션 생성
alembic revision --autogenerate -m "Initial schema"

# 마이그레이션 실행
alembic upgrade head
```

이 스키마 설계를 통해 PostgreSQL 기반의 안정적이고 확장 가능한 메타데이터 관리 시스템을 구축할 수 있습니다.
