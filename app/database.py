"""
데이터베이스 연결 및 모델 관리
SQLite 메타데이터 데이터베이스 설정
"""

from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime, Text, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.sql import func
from datetime import datetime
from typing import Generator
import uuid

from app.config import settings

# SQLAlchemy 설정
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 데이터베이스 모델 정의
class Database(Base):
    """데이터베이스 정보 모델"""
    __tablename__ = "databases"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, unique=True)
    display_name = Column(String(255), nullable=False)
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False, default=5432)
    database_name = Column(String(255), nullable=False)
    username = Column(String(255), nullable=False)
    password_encrypted = Column(Text, nullable=False)
    ssl_mode = Column(String(20), default='require')
    environment = Column(String(20), nullable=False)  # production, staging, development
    priority = Column(String(10), nullable=False)     # high, medium, low
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    last_connection_test = Column(DateTime)
    connection_status = Column(String(20), default='unknown')  # connected, disconnected, error, unknown

class BackupConfig(Base):
    """백업 설정 모델"""
    __tablename__ = "backup_configs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    database_id = Column(String, nullable=False)
    full_backup_schedule = Column(String(100))  # cron 표현식
    incremental_schedule = Column(String(100))  # cron 표현식
    compression_algorithm = Column(String(20), default='gzip')  # gzip, lz4, zstd
    encryption_enabled = Column(Boolean, default=True)
    retention_daily = Column(Integer, default=7)
    retention_weekly = Column(Integer, default=4)
    retention_monthly = Column(Integer, default=12)
    backup_timeout = Column(Integer, default=3600)  # 초 단위
    max_parallel_jobs = Column(Integer, default=1)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class Backup(Base):
    """백업 실행 이력 모델"""
    __tablename__ = "backups"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    database_id = Column(String, nullable=False)
    backup_type = Column(String(20), nullable=False)  # full, incremental, pitr, schema, data
    status = Column(String(20), nullable=False)       # pending, running, completed, failed, cancelled
    file_path = Column(Text)
    file_size = Column(Integer)        # 바이트 단위
    compressed_size = Column(Integer)  # 바이트 단위
    compression_ratio = Column(Float)
    is_encrypted = Column(Boolean, default=False)
    checksum = Column(String(64))      # SHA-256 해시
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration_seconds = Column(Integer)
    error_message = Column(Text)
    pg_dump_version = Column(String(20))
    database_size = Column(Integer)    # 백업 시점의 DB 크기
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class Schedule(Base):
    """스케줄 정보 모델"""
    __tablename__ = "schedules"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    database_id = Column(String, nullable=False)
    schedule_type = Column(String(20), nullable=False)  # full, incremental
    cron_expression = Column(String(100), nullable=False)
    timezone = Column(String(50), default='UTC')
    is_active = Column(Boolean, default=True)
    next_run = Column(DateTime)
    last_run = Column(DateTime)
    run_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class Notification(Base):
    """알림 이력 모델"""
    __tablename__ = "notifications"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    database_id = Column(String)
    backup_id = Column(String)
    notification_type = Column(String(20), nullable=False)  # email, slack, discord, webhook
    level = Column(String(10), nullable=False)              # info, warning, critical
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    recipient = Column(String(255))
    status = Column(String(20), default='pending')          # pending, sent, failed
    sent_at = Column(DateTime)
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())

class SystemLog(Base):
    """시스템 로그 모델"""
    __tablename__ = "system_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    level = Column(String(10), nullable=False)      # debug, info, warning, error, critical
    component = Column(String(50), nullable=False)  # backup_engine, scheduler, api, etc.
    message = Column(Text, nullable=False)
    details = Column(Text)  # JSON 형태의 상세 정보
    database_id = Column(String)
    backup_id = Column(String)
    user_id = Column(String(100))  # 향후 사용자 관리용
    ip_address = Column(String(45))
    created_at = Column(DateTime, default=func.now())

# 데이터베이스 초기화 함수
async def init_database():
    """데이터베이스 테이블 생성"""
    Base.metadata.create_all(bind=engine)

def get_db() -> Generator[Session, None, None]:
    """데이터베이스 세션 의존성"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 데이터베이스 유틸리티 함수
def create_database_record(db: Session, **kwargs) -> Database:
    """새 데이터베이스 레코드 생성"""
    db_record = Database(**kwargs)
    db.add(db_record)
    db.commit()
    db.refresh(db_record)
    return db_record

def get_database_by_id(db: Session, db_id: str) -> Database:
    """ID로 데이터베이스 조회"""
    return db.query(Database).filter(Database.id == db_id).first()

def get_all_databases(db: Session) -> list[Database]:
    """모든 활성 데이터베이스 조회"""
    return db.query(Database).filter(Database.is_active == True).all()

def create_backup_record(db: Session, **kwargs) -> Backup:
    """새 백업 레코드 생성"""
    backup_record = Backup(**kwargs)
    db.add(backup_record)
    db.commit()
    db.refresh(backup_record)
    return backup_record

def get_backups_by_database(db: Session, database_id: str, limit: int = 50) -> list[Backup]:
    """특정 데이터베이스의 백업 이력 조회"""
    return db.query(Backup).filter(
        Backup.database_id == database_id
    ).order_by(Backup.created_at.desc()).limit(limit).all()

def log_system_event(db: Session, level: str, component: str, message: str, **kwargs):
    """시스템 이벤트 로그 기록"""
    log_record = SystemLog(
        level=level,
        component=component,
        message=message,
        **kwargs
    )
    db.add(log_record)
    db.commit()
