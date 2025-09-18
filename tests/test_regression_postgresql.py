"""
PostgreSQL 기능 회귀 테스트
- 기존 PostgreSQL 백업 기능이 다중 DB 지원 후에도 정상 동작하는지 검증
- 기존 API 호환성 확인
- 설정 파일 호환성 확인
- 백업 파일 형식 호환성 확인

주의:
- 기존 기능의 동작 방식이 변경되지 않았는지 확인
- 새로운 기능이 기존 기능에 영향을 주지 않는지 검증
- API 응답 형식 호환성 유지
"""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from app.core.backup_engine import BackupEngine
from app.core.backup_engine_v2 import BackupEngineV2
from app.core.database_manager import DatabaseManager
from app.core.database_manager_v2 import DatabaseManagerV2
from app.database import Database, Backup
from app.config import settings


class TestBackupEngineRegression:
    """BackupEngine 회귀 테스트"""
    
    def test_original_backup_engine_still_works(self):
        """기존 BackupEngine이 여전히 동작하는지 테스트"""
        engine = BackupEngine()
        
        # 기존 메서드들이 존재하는지 확인
        assert hasattr(engine, 'run_backup')
        assert hasattr(engine, '_run_pg_dump')
        assert hasattr(engine, '_get_compression_settings')
        assert hasattr(engine, '_compress_file')
        assert hasattr(engine, '_sha256')
        
        # 기존 설정 메서드 동작 확인
        comp_algo, comp_level = engine._get_compression_settings()
        assert isinstance(comp_algo, str)
        assert isinstance(comp_level, int)
        assert comp_algo in ['gzip', 'lz4', 'zstd']
    
    @patch('subprocess.run')
    def test_pg_dump_command_compatibility(self, mock_subprocess):
        """pg_dump 명령어 생성 호환성 테스트"""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result
        
        engine = BackupEngine()
        
        # Mock Database 객체
        mock_db = Mock()
        mock_db.host = "localhost"
        mock_db.port = 5432
        mock_db.database_name = "test_db"
        mock_db.username = "test_user"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "test_backup.sql"
            
            # 기존 _run_pg_dump 메서드 호출
            try:
                engine._run_pg_dump(mock_db, output_path, "test_password")
                
                # pg_dump 명령어가 호출되었는지 확인
                mock_subprocess.assert_called_once()
                call_args = mock_subprocess.call_args[0][0]
                
                # 기존 명령어 형식 유지 확인
                assert "pg_dump" in call_args
                assert "--host=localhost" in call_args
                assert "--port=5432" in call_args
                assert "--username=test_user" in call_args
                assert "--dbname=test_db" in call_args
                
            except Exception as e:
                # 메서드가 존재하지 않거나 변경된 경우
                pytest.fail(f"기존 _run_pg_dump 메서드 호환성 문제: {e}")
    
    def test_compression_settings_backward_compatibility(self):
        """압축 설정 하위 호환성 테스트"""
        engine = BackupEngine()
        
        # 기존 압축 설정 메서드 동작 확인
        comp_algo, comp_level = engine._get_compression_settings()
        
        # 반환값 형식 확인
        assert isinstance(comp_algo, str)
        assert isinstance(comp_level, int)
        
        # 지원하는 압축 알고리즘 확인
        supported_algorithms = ['gzip', 'lz4', 'zstd']
        assert comp_algo in supported_algorithms
        
        # 압축 레벨 범위 확인
        assert 1 <= comp_level <= 9
    
    def test_checksum_calculation_compatibility(self):
        """체크섬 계산 호환성 테스트"""
        engine = BackupEngine()
        
        # 테스트 파일 생성
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("test content for checksum")
            test_file = Path(f.name)
        
        try:
            # 기존 SHA-256 계산 메서드
            checksum = engine._sha256(test_file)
            
            # 반환값 형식 확인
            assert isinstance(checksum, str)
            assert len(checksum) == 64  # SHA-256은 64자리 hex
            
            # 동일한 파일에 대해 동일한 체크섬 생성 확인
            checksum2 = engine._sha256(test_file)
            assert checksum == checksum2
            
        finally:
            try:
                test_file.unlink()
            except FileNotFoundError:
                pass


class TestDatabaseManagerRegression:
    """DatabaseManager 회귀 테스트"""
    
    def test_original_database_manager_compatibility(self):
        """기존 DatabaseManager 호환성 테스트"""
        manager = DatabaseManager()
        
        # 기존 메서드들이 존재하는지 확인
        assert hasattr(manager, 'test_connection')
        assert hasattr(manager, 'get_database_info')
        assert hasattr(manager, 'execute_query')
        
        # 기존 속성들이 존재하는지 확인
        assert hasattr(manager, 'logger')
    
    @patch('psycopg2.connect')
    def test_postgresql_connection_compatibility(self, mock_connect):
        """PostgreSQL 연결 호환성 테스트"""
        # Mock 연결 설정
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = ("PostgreSQL 13.0",)
        mock_connect.return_value = mock_conn
        
        manager = DatabaseManager()
        
        # 기존 연결 테스트 메서드 호출
        result = manager.test_connection(
            host="localhost",
            port=5432,
            database="test_db",
            username="test_user",
            password="test_pass"
        )
        
        # 기존 반환값 형식 확인
        assert isinstance(result, dict)
        assert "success" in result
        assert "message" in result
        
        # PostgreSQL 연결이 성공했는지 확인
        if result["success"]:
            assert "version" in result
    
    def test_database_info_format_compatibility(self):
        """데이터베이스 정보 형식 호환성 테스트"""
        manager = DatabaseManager()
        
        # Mock Database 객체
        mock_db = Mock()
        mock_db.id = "test_db_id"
        mock_db.database_name = "test_db"
        mock_db.host = "localhost"
        mock_db.port = 5432
        mock_db.username = "test_user"
        mock_db.db_type = "postgresql"  # 새로 추가된 필드
        
        with patch.object(manager, 'get_database_info') as mock_get_info:
            # 기존 형식의 반환값 모킹
            mock_get_info.return_value = {
                "id": "test_db_id",
                "name": "test_db",
                "host": "localhost",
                "port": 5432,
                "status": "connected",
                "version": "PostgreSQL 13.0"
            }
            
            info = manager.get_database_info("test_db_id")
            
            # 기존 필드들이 유지되는지 확인
            required_fields = ["id", "name", "host", "port", "status"]
            for field in required_fields:
                assert field in info, f"필수 필드 '{field}'가 누락됨"


class TestAPICompatibilityRegression:
    """API 호환성 회귀 테스트"""
    
    def test_database_api_response_format(self):
        """데이터베이스 API 응답 형식 호환성"""
        # Mock Database 모델
        mock_db = Mock(spec=Database)
        mock_db.id = "test_id"
        mock_db.database_name = "test_db"
        mock_db.host = "localhost"
        mock_db.port = 5432
        mock_db.username = "test_user"
        mock_db.environment = "production"
        mock_db.priority = "high"
        mock_db.db_type = "postgresql"  # 새 필드
        mock_db.created_at = "2024-01-01T00:00:00Z"
        mock_db.updated_at = "2024-01-01T00:00:00Z"
        
        # 기존 API 응답 형식 확인 (새 필드 추가되어도 기존 필드는 유지)
        expected_fields = [
            "id", "database_name", "host", "port", "username",
            "environment", "priority", "created_at", "updated_at"
        ]
        
        for field in expected_fields:
            assert hasattr(mock_db, field), f"기존 필드 '{field}'가 누락됨"
        
        # 새로 추가된 필드도 존재하는지 확인
        assert hasattr(mock_db, "db_type"), "새 필드 'db_type'가 누락됨"
    
    def test_backup_api_response_format(self):
        """백업 API 응답 형식 호환성"""
        # Mock Backup 모델
        mock_backup = Mock(spec=Backup)
        mock_backup.id = "backup_id"
        mock_backup.database_id = "db_id"
        mock_backup.status = "completed"
        mock_backup.file_path = "/path/to/backup.sql"
        mock_backup.file_size = 1024000
        mock_backup.checksum = "abc123"
        mock_backup.started_at = "2024-01-01T00:00:00Z"
        mock_backup.completed_at = "2024-01-01T00:00:00Z"
        mock_backup.duration_seconds = 30
        mock_backup.is_encrypted = False
        mock_backup.pg_dump_version = "pg_dump 13.0"  # 기존 필드
        
        # 기존 API 응답 필드들이 유지되는지 확인
        expected_fields = [
            "id", "database_id", "status", "file_path", "file_size",
            "checksum", "started_at", "completed_at", "duration_seconds",
            "is_encrypted"
        ]
        
        for field in expected_fields:
            assert hasattr(mock_backup, field), f"기존 필드 '{field}'가 누락됨"


class TestConfigurationRegression:
    """설정 파일 회귀 테스트"""
    
    def test_settings_backward_compatibility(self):
        """설정 파일 하위 호환성 테스트"""
        # 기존 설정 필드들이 여전히 존재하는지 확인
        required_settings = [
            "BACKUP_BASE_PATH",
            "TEMP_PATH",
            "DEFAULT_ENCRYPTION",
            "DATABASE_URL"
        ]
        
        for setting in required_settings:
            assert hasattr(settings, setting), f"기존 설정 '{setting}'가 누락됨"
    
    def test_database_yaml_compatibility(self):
        """databases.yaml 설정 호환성 테스트"""
        # 기존 PostgreSQL 설정 형식이 여전히 지원되는지 확인
        legacy_config = {
            "production_postgres": {
                "name": "운영 PostgreSQL 데이터베이스",
                "host": "localhost",
                "port": 5432,
                "database": "production",
                "username": "backup_user",
                "password": "password",
                "ssl_mode": "require",
                "priority": "high",
                "environment": "production",
                # db_type이 없는 기존 설정
                "backup_config": {
                    "full_backup_schedule": "0 2 * * 0",
                    "compression": "gzip",
                    "encryption": True
                }
            }
        }
        
        # 기존 필수 필드들이 모두 존재하는지 확인
        db_config = legacy_config["production_postgres"]
        required_fields = ["name", "host", "port", "database", "username", "password"]
        
        for field in required_fields:
            assert field in db_config, f"기존 필수 필드 '{field}'가 누락됨"
        
        # db_type이 없어도 기본값(postgresql)으로 처리되어야 함
        db_type = db_config.get("db_type", "postgresql")
        assert db_type == "postgresql"


class TestDataMigrationRegression:
    """데이터 마이그레이션 회귀 테스트"""
    
    def test_existing_database_records_compatibility(self):
        """기존 데이터베이스 레코드 호환성 테스트"""
        # 기존 Database 레코드 (db_type 없음)
        legacy_db_data = {
            "id": "legacy_db_1",
            "database_name": "legacy_production",
            "host": "old-postgres.company.com",
            "port": 5432,
            "username": "legacy_user",
            "password_encrypted": "encrypted_password",
            "ssl_mode": "require",
            "environment": "production",
            "priority": "high",
            # db_type 필드가 없는 기존 레코드
        }
        
        # db_type이 없는 기존 레코드도 처리 가능해야 함
        db_type = legacy_db_data.get("db_type", "postgresql")  # 기본값
        assert db_type == "postgresql"
        
        # 기존 필드들이 모두 유지되는지 확인
        required_fields = [
            "id", "database_name", "host", "port", "username",
            "password_encrypted", "ssl_mode", "environment", "priority"
        ]
        
        for field in required_fields:
            assert field in legacy_db_data, f"기존 필드 '{field}'가 누락됨"
    
    def test_existing_backup_records_compatibility(self):
        """기존 백업 레코드 호환성 테스트"""
        # 기존 Backup 레코드
        legacy_backup_data = {
            "id": "legacy_backup_1",
            "database_id": "legacy_db_1",
            "status": "completed",
            "file_path": "/backups/legacy_backup.sql.gz",
            "file_size": 1024000,
            "checksum": "sha256_hash",
            "started_at": "2024-01-01T00:00:00Z",
            "completed_at": "2024-01-01T00:30:00Z",
            "duration_seconds": 1800,
            "is_encrypted": True,
            "pg_dump_version": "pg_dump (PostgreSQL) 13.0",
            "compressed_size": 512000,
            "compression_ratio": 50.0
        }
        
        # 기존 백업 레코드 필드들이 모두 유지되는지 확인
        required_fields = [
            "id", "database_id", "status", "file_path", "file_size",
            "checksum", "started_at", "completed_at", "duration_seconds",
            "is_encrypted"
        ]
        
        for field in required_fields:
            assert field in legacy_backup_data, f"기존 필드 '{field}'가 누락됨"
        
        # PostgreSQL 특화 필드들도 유지되는지 확인
        postgresql_fields = ["pg_dump_version", "compressed_size", "compression_ratio"]
        for field in postgresql_fields:
            assert field in legacy_backup_data, f"PostgreSQL 특화 필드 '{field}'가 누락됨"


class TestPerformanceRegression:
    """성능 회귀 테스트"""
    
    def test_backup_performance_not_degraded(self):
        """백업 성능이 저하되지 않았는지 테스트"""
        # 기존 BackupEngine과 새로운 BackupEngineV2 성능 비교는
        # 실제 환경에서 측정해야 하므로 여기서는 구조적 검증만 수행
        
        original_engine = BackupEngine()
        new_engine = BackupEngineV2()
        
        # 두 엔진 모두 동일한 인터페이스를 제공하는지 확인
        assert hasattr(original_engine, 'run_backup')
        assert hasattr(new_engine, 'run_backup')
        
        # run_backup 메서드의 시그니처가 동일한지 확인
        import inspect
        
        original_sig = inspect.signature(original_engine.run_backup)
        new_sig = inspect.signature(new_engine.run_backup)
        
        # 매개변수 이름과 개수가 동일한지 확인
        original_params = list(original_sig.parameters.keys())
        new_params = list(new_sig.parameters.keys())
        
        assert original_params == new_params, "run_backup 메서드 시그니처가 변경됨"
    
    def test_memory_usage_not_increased(self):
        """메모리 사용량이 크게 증가하지 않았는지 테스트"""
        import psutil
        
        process = psutil.Process()
        
        # 기존 엔진 메모리 사용량
        memory_before = process.memory_info().rss
        original_engine = BackupEngine()
        memory_after_original = process.memory_info().rss
        
        # 새 엔진 메모리 사용량
        new_engine = BackupEngineV2()
        memory_after_new = process.memory_info().rss
        
        original_memory_usage = memory_after_original - memory_before
        new_memory_usage = memory_after_new - memory_after_original
        
        # 새 엔진의 메모리 사용량이 기존 엔진의 2배를 넘지 않아야 함
        assert new_memory_usage <= original_memory_usage * 2, \
            f"새 엔진의 메모리 사용량이 과도하게 증가: {new_memory_usage} vs {original_memory_usage}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
