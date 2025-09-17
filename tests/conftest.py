"""
테스트 설정 및 픽스처
"""

import os
import sys
import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from unittest.mock import Mock

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.main import app
from app.database import Base, get_db
from app.config import settings


# 테스트 데이터베이스 설정
TEST_DATABASE_URL = "sqlite:///./test.db"


@pytest.fixture(scope="session")
def test_engine():
    """테스트용 데이터베이스 엔진"""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    # 테스트 완료 후 정리
    if os.path.exists("./test.db"):
        os.remove("./test.db")


@pytest.fixture(scope="function")
def test_db(test_engine):
    """테스트용 데이터베이스 세션"""
    TestingSessionLocal = sessionmaker(
        autocommit=False, 
        autoflush=False, 
        bind=test_engine
    )
    
    # 각 테스트마다 트랜잭션 롤백
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(test_db):
    """테스트용 FastAPI 클라이언트"""
    def override_get_db():
        try:
            yield test_db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def temp_dir():
    """임시 디렉토리"""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture(scope="function")
def mock_pg_dump():
    """pg_dump 명령어 모킹"""
    mock = Mock()
    mock.return_value.returncode = 0
    mock.return_value.stdout = b"-- PostgreSQL database dump"
    mock.return_value.stderr = b""
    return mock


@pytest.fixture(scope="function")
def sample_database_data():
    """테스트용 데이터베이스 정보"""
    return {
        "name": "test_db",
        "display_name": "테스트 데이터베이스",
        "host": "localhost",
        "port": 5432,
        "database_name": "testdb",
        "username": "testuser",
        "password_encrypted": "testpass",
        "ssl_mode": "require",
        "environment": "development",
        "priority": "medium",
        "is_active": True
    }


@pytest.fixture(scope="function")
def sample_backup_data():
    """테스트용 백업 정보"""
    return {
        "database_id": "test-db-id",
        "backup_type": "full",
        "status": "completed",
        "file_path": "/tmp/test_backup.sql.gz",
        "file_size": 1024,
        "compressed_size": 512,
        "compression_ratio": 0.5,
        "is_encrypted": True,
        "checksum": "abc123def456",
        "pg_dump_version": "14.0"
    }


@pytest.fixture(scope="function")
def sample_user_data():
    """테스트용 사용자 정보"""
    return {
        "username": "testuser",
        "full_name": "테스트 사용자",
        "password_hash": "hashed_password",
        "password_salt": "salt123",
        "role": "admin",
        "is_active": True
    }


@pytest.fixture(scope="function")
def sample_audit_data():
    """테스트용 감사 로그 정보"""
    return {
        "user_id": "test-user-id",
        "username": "testuser",
        "action": "CREATE",
        "resource_type": "database",
        "resource_id": "test-resource-id",
        "resource_name": "테스트 리소스",
        "ip_address": "127.0.0.1",
        "status": "SUCCESS"
    }


# 환경 변수 설정
@pytest.fixture(autouse=True)
def setup_test_env():
    """테스트 환경 변수 설정"""
    os.environ["TESTING"] = "true"
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    os.environ["DEBUG"] = "true"
    yield
    # 정리
    if "TESTING" in os.environ:
        del os.environ["TESTING"]


# 비동기 테스트 설정
pytest_plugins = ('pytest_asyncio',)


@pytest.fixture(scope="session")
def event_loop():
    """이벤트 루프 설정"""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# 테스트 데이터 팩토리
class DatabaseFactory:
    """데이터베이스 테스트 데이터 팩토리"""
    
    @staticmethod
    def create(db, **kwargs):
        from app.database import Database
        
        default_data = {
            "name": "test_db",
            "display_name": "테스트 데이터베이스",
            "host": "localhost",
            "port": 5432,
            "database_name": "testdb",
            "username": "testuser",
            "password_encrypted": "testpass",
            "ssl_mode": "require",
            "environment": "development",
            "priority": "medium",
            "is_active": True
        }
        default_data.update(kwargs)
        
        database = Database(**default_data)
        db.add(database)
        db.commit()
        db.refresh(database)
        return database


class BackupFactory:
    """백업 테스트 데이터 팩토리"""
    
    @staticmethod
    def create(db, **kwargs):
        from app.database import Backup
        
        default_data = {
            "database_id": "test-db-id",
            "backup_type": "full",
            "status": "completed",
            "file_path": "/tmp/test_backup.sql.gz",
            "file_size": 1024,
            "compressed_size": 512,
            "compression_ratio": 0.5,
            "is_encrypted": True,
            "checksum": "abc123def456",
            "pg_dump_version": "14.0"
        }
        default_data.update(kwargs)
        
        backup = Backup(**default_data)
        db.add(backup)
        db.commit()
        db.refresh(backup)
        return backup


class UserFactory:
    """사용자 테스트 데이터 팩토리"""
    
    @staticmethod
    def create(db, **kwargs):
        from app.database import User
        
        default_data = {
            "username": "testuser",
            "full_name": "테스트 사용자",
            "password_hash": "hashed_password",
            "password_salt": "salt123",
            "role": "admin",
            "is_active": True
        }
        default_data.update(kwargs)
        
        user = User(**default_data)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


@pytest.fixture
def database_factory():
    return DatabaseFactory


@pytest.fixture
def backup_factory():
    return BackupFactory


@pytest.fixture
def user_factory():
    return UserFactory
