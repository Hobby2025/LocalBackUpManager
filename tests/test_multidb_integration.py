"""
다중 DB 통합 테스트
- PostgreSQL, MySQL, SQLite 연결 테스트
- E2E 백업 시나리오 테스트
- 어댑터 패턴 통합 검증

주의:
- 실제 DB 연결이 필요한 통합 테스트
- 테스트 환경 설정 필요
- 각 DB별 테스트 데이터 준비
"""

import os
import pytest
import tempfile
import sqlite3
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch

from app.core.database_adapters import (
    create_database_adapter,
    PostgresAdapter,
    MySQLAdapter,
    SQLiteAdapter
)
from app.core.backup_adapters import (
    create_backup_adapter,
    PostgresBackupAdapter,
    MySQLBackupAdapter,
    SQLiteBackupAdapter
)
from app.core.backup_postprocessor import backup_postprocessor


class TestDatabaseAdapterIntegration:
    """데이터베이스 어댑터 통합 테스트"""
    
    def test_create_database_adapter_postgresql(self):
        """PostgreSQL 어댑터 생성 테스트"""
        adapter = create_database_adapter("postgresql", "test_db_1")
        assert isinstance(adapter, PostgresAdapter)
        assert adapter.database_id == "test_db_1"
    
    def test_create_database_adapter_mysql(self):
        """MySQL 어댑터 생성 테스트"""
        adapter = create_database_adapter("mysql", "test_db_2")
        assert isinstance(adapter, MySQLAdapter)
        assert adapter.database_id == "test_db_2"
    
    def test_create_database_adapter_sqlite(self):
        """SQLite 어댑터 생성 테스트"""
        adapter = create_database_adapter("sqlite", "test_db_3")
        assert isinstance(adapter, SQLiteAdapter)
        assert adapter.database_id == "test_db_3"
    
    def test_create_database_adapter_invalid_type(self):
        """지원하지 않는 DB 타입 테스트"""
        with pytest.raises(ValueError, match="지원하지 않는 데이터베이스 타입"):
            create_database_adapter("oracle", "test_db_4")


class TestBackupAdapterIntegration:
    """백업 어댑터 통합 테스트"""
    
    def test_create_backup_adapter_postgresql(self):
        """PostgreSQL 백업 어댑터 생성 테스트"""
        adapter = create_backup_adapter("postgresql", "test_backup_1")
        assert isinstance(adapter, PostgresBackupAdapter)
        assert adapter.database_id == "test_backup_1"
    
    def test_create_backup_adapter_mysql(self):
        """MySQL 백업 어댑터 생성 테스트"""
        adapter = create_backup_adapter("mysql", "test_backup_2")
        assert isinstance(adapter, MySQLBackupAdapter)
        assert adapter.database_id == "test_backup_2"
    
    def test_create_backup_adapter_sqlite(self):
        """SQLite 백업 어댑터 생성 테스트"""
        adapter = create_backup_adapter("sqlite", "test_backup_3")
        assert isinstance(adapter, SQLiteBackupAdapter)
        assert adapter.database_id == "test_backup_3"
    
    def test_create_backup_adapter_invalid_type(self):
        """지원하지 않는 DB 타입 테스트"""
        with pytest.raises(ValueError, match="지원하지 않는 데이터베이스 타입"):
            create_backup_adapter("mongodb", "test_backup_4")


class TestPostgreSQLIntegration:
    """PostgreSQL 통합 테스트"""
    
    @pytest.fixture
    def postgres_config(self):
        """PostgreSQL 테스트 설정"""
        return {
            "host": os.getenv("TEST_POSTGRES_HOST", "localhost"),
            "port": int(os.getenv("TEST_POSTGRES_PORT", "5432")),
            "dbname": os.getenv("TEST_POSTGRES_DB", "test_db"),
            "user": os.getenv("TEST_POSTGRES_USER", "test_user"),
            "password": os.getenv("TEST_POSTGRES_PASSWORD", "test_pass"),
            "sslmode": "disable"
        }
    
    def test_postgres_backup_command_generation(self, postgres_config):
        """PostgreSQL 백업 명령어 생성 테스트"""
        adapter = PostgresBackupAdapter("test_pg")
        output_path = Path("/tmp/test_backup.sql")
        
        cmd = adapter.get_backup_command(
            host=postgres_config["host"],
            port=postgres_config["port"],
            dbname=postgres_config["dbname"],
            user=postgres_config["user"],
            password=postgres_config["password"],
            output_path=output_path
        )
        
        assert "pg_dump" in cmd
        assert f"--host={postgres_config['host']}" in cmd
        assert f"--port={postgres_config['port']}" in cmd
        assert f"--username={postgres_config['user']}" in cmd
        assert f"--dbname={postgres_config['dbname']}" in cmd
        assert f"--file={output_path}" in cmd
    
    def test_postgres_options_validation(self):
        """PostgreSQL 옵션 검증 테스트"""
        adapter = PostgresBackupAdapter("test_pg")
        
        # 기본 옵션 테스트
        options = adapter.validate_options(None)
        assert options["format"] == "custom"
        assert options["compress"] == 6
        assert options["verbose"] is True
        
        # 커스텀 옵션 테스트
        custom_options = {"format": "plain", "compress": 9}
        options = adapter.validate_options(custom_options)
        assert options["format"] == "plain"
        assert options["compress"] == 9
        assert options["verbose"] is True  # 기본값 유지


class TestMySQLIntegration:
    """MySQL 통합 테스트"""
    
    @pytest.fixture
    def mysql_config(self):
        """MySQL 테스트 설정"""
        return {
            "host": os.getenv("TEST_MYSQL_HOST", "localhost"),
            "port": int(os.getenv("TEST_MYSQL_PORT", "3306")),
            "dbname": os.getenv("TEST_MYSQL_DB", "test_db"),
            "user": os.getenv("TEST_MYSQL_USER", "test_user"),
            "password": os.getenv("TEST_MYSQL_PASSWORD", "test_pass")
        }
    
    def test_mysql_backup_command_generation(self, mysql_config):
        """MySQL 백업 명령어 생성 테스트"""
        adapter = MySQLBackupAdapter("test_mysql")
        output_path = Path("/tmp/test_backup.sql")
        
        cmd = adapter.get_backup_command(
            host=mysql_config["host"],
            port=mysql_config["port"],
            dbname=mysql_config["dbname"],
            user=mysql_config["user"],
            password=mysql_config["password"],
            output_path=output_path
        )
        
        assert "mysqldump" in cmd
        assert f"--host={mysql_config['host']}" in cmd
        assert f"--port={mysql_config['port']}" in cmd
        assert f"--user={mysql_config['user']}" in cmd
        assert f"--password={mysql_config['password']}" in cmd
        assert f"--result-file={output_path}" in cmd
        assert mysql_config["dbname"] in cmd
    
    def test_mysql_options_validation(self):
        """MySQL 옵션 검증 테스트"""
        adapter = MySQLBackupAdapter("test_mysql")
        
        # 기본 옵션 테스트
        options = adapter.validate_options(None)
        assert options["single_transaction"] is True
        assert options["routines"] is True
        assert options["triggers"] is True
        
        # 커스텀 옵션 테스트
        custom_options = {"single_transaction": False, "routines": False}
        options = adapter.validate_options(custom_options)
        assert options["single_transaction"] is False
        assert options["routines"] is False
        assert options["triggers"] is True  # 기본값 유지


class TestSQLiteIntegration:
    """SQLite 통합 테스트"""
    
    @pytest.fixture
    def sqlite_test_db(self):
        """SQLite 테스트 데이터베이스 생성"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        # 테스트 데이터 생성
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE test_table (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("INSERT INTO test_table (name) VALUES ('test_data_1')")
        cursor.execute("INSERT INTO test_table (name) VALUES ('test_data_2')")
        conn.commit()
        conn.close()
        
        yield db_path
        
        # 정리
        try:
            os.unlink(db_path)
        except FileNotFoundError:
            pass
    
    def test_sqlite_backup_api_method(self, sqlite_test_db):
        """SQLite backup API 방식 테스트"""
        adapter = SQLiteBackupAdapter("test_sqlite")
        
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            backup_path = Path(f.name)
        
        try:
            success, error, metadata = adapter._backup_using_api(
                Path(sqlite_test_db), backup_path, {"vacuum": False, "wal_checkpoint": False, "verify_integrity": False}
            )
            
            assert success is True
            assert error == ""
            assert metadata["backup_tool"] == "sqlite3_backup_api"
            assert backup_path.exists()
            assert backup_path.stat().st_size > 0
            
        finally:
            try:
                backup_path.unlink()
            except FileNotFoundError:
                pass
    
    def test_sqlite_file_copy_method(self, sqlite_test_db):
        """SQLite 파일 복사 방식 테스트"""
        adapter = SQLiteBackupAdapter("test_sqlite")
        
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            backup_path = Path(f.name)
        
        try:
            success, error, metadata = adapter._backup_using_file_copy(
                Path(sqlite_test_db), backup_path, {"wal_checkpoint": False}
            )
            
            assert success is True
            assert error == ""
            assert metadata["backup_tool"] == "file_copy"
            assert backup_path.exists()
            assert backup_path.stat().st_size > 0
            
        finally:
            try:
                backup_path.unlink()
            except FileNotFoundError:
                pass
    
    def test_sqlite_options_validation(self):
        """SQLite 옵션 검증 테스트"""
        adapter = SQLiteBackupAdapter("test_sqlite")
        
        # 기본 옵션 테스트
        options = adapter.validate_options(None)
        assert options["method"] == "backup_api"
        assert options["vacuum"] is True
        assert options["wal_checkpoint"] is True
        
        # 커스텀 옵션 테스트
        custom_options = {"method": "file_copy", "vacuum": False}
        options = adapter.validate_options(custom_options)
        assert options["method"] == "file_copy"
        assert options["vacuum"] is False
        assert options["wal_checkpoint"] is True  # 기본값 유지


class TestBackupPostProcessorIntegration:
    """백업 후처리 통합 테스트"""
    
    @pytest.fixture
    def test_file(self):
        """테스트용 파일 생성"""
        with tempfile.NamedTemporaryFile(mode='w', suffix=".txt", delete=False) as f:
            f.write("This is a test file for backup post-processing.\n" * 100)
            test_file_path = Path(f.name)
        
        yield test_file_path
        
        # 정리
        try:
            test_file_path.unlink()
        except FileNotFoundError:
            pass
    
    def test_compression_tools_detection(self):
        """압축 도구 감지 테스트"""
        tools = backup_postprocessor.get_available_compression_tools()
        
        # gzip은 항상 사용 가능해야 함 (파이썬 내장)
        assert tools["gzip"] is True
        
        # 다른 도구들은 시스템에 따라 다름
        assert isinstance(tools["lz4"], bool)
        assert isinstance(tools["zstd"], bool)
    
    def test_gzip_compression(self, test_file):
        """gzip 압축 테스트"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "compressed.gz"
            
            success, error, metadata = backup_postprocessor.compress_file(
                test_file, output_path, "gzip", 6
            )
            
            assert success is True
            assert error == ""
            assert metadata["compression_tool"] == "gzip"
            assert output_path.exists()
            assert output_path.stat().st_size < test_file.stat().st_size
    
    def test_checksum_calculation(self, test_file):
        """체크섬 계산 테스트"""
        success, checksum, metadata = backup_postprocessor.calculate_checksum(
            test_file, "sha256"
        )
        
        assert success is True
        assert len(checksum) == 64  # SHA-256은 64자리 hex
        assert metadata["checksum_algorithm"] == "sha256"
        assert metadata["file_size_bytes"] == test_file.stat().st_size
    
    @patch('app.core.backup_postprocessor.BackupPostProcessor._get_active_encryption_key_info')
    def test_integrated_postprocessing(self, mock_key_info, test_file):
        """통합 후처리 파이프라인 테스트"""
        # 암호화 키 모킹
        mock_key_info.return_value = ("test_key_id", "a" * 32)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            
            success, final_path, metadata = backup_postprocessor.process_backup_file(
                input_path=test_file,
                output_dir=output_dir,
                compress=True,
                compression_type="gzip",
                encrypt=True,
                calculate_checksum=True,
                cleanup_intermediate=True
            )
            
            assert success is True
            assert Path(final_path).exists()
            assert metadata["processing_steps"]["compressed"] is True
            assert metadata["processing_steps"]["encrypted"] is True
            assert metadata["processing_steps"]["checksum_calculated"] is True
            assert "checksum" in metadata


class TestE2EBackupScenarios:
    """E2E 백업 시나리오 테스트"""
    
    def test_sqlite_full_backup_scenario(self):
        """SQLite 전체 백업 시나리오 테스트"""
        # 1. 테스트 DB 생성
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        cursor.execute("INSERT INTO users (name) VALUES ('Alice'), ('Bob')")
        conn.commit()
        conn.close()
        
        try:
            # 2. 백업 어댑터로 백업 실행
            adapter = create_backup_adapter("sqlite", "test_e2e")
            
            with tempfile.TemporaryDirectory() as temp_dir:
                backup_path = Path(temp_dir) / "backup.db"
                
                success, error, metadata = adapter.run_backup(
                    host="localhost",
                    port=0,
                    dbname=db_path,
                    user="",
                    password="",
                    output_path=backup_path
                )
                
                # 3. 백업 성공 검증
                assert success is True
                assert error == ""
                assert backup_path.exists()
                assert metadata["backup_tool"] in ["sqlite3_backup_api", "file_copy", "sqlite3_dump"]
                
                # 4. 백업된 데이터 검증
                if metadata["backup_tool"] in ["sqlite3_backup_api", "file_copy"]:
                    backup_conn = sqlite3.connect(backup_path)
                    backup_cursor = backup_conn.cursor()
                    backup_cursor.execute("SELECT COUNT(*) FROM users")
                    count = backup_cursor.fetchone()[0]
                    assert count == 2
                    backup_conn.close()
        
        finally:
            try:
                os.unlink(db_path)
            except FileNotFoundError:
                pass
    
    @patch('subprocess.run')
    def test_postgresql_backup_scenario_mock(self, mock_subprocess):
        """PostgreSQL 백업 시나리오 테스트 (모킹)"""
        # subprocess.run 모킹
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "pg_dump completed successfully"
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result
        
        adapter = create_backup_adapter("postgresql", "test_pg_e2e")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_path = Path(temp_dir) / "backup.sql"
            
            # 백업 파일 생성 (모킹을 위해)
            backup_path.write_text("-- PostgreSQL database dump\nCREATE TABLE test();")
            
            success, error, metadata = adapter.run_backup(
                host="localhost",
                port=5432,
                dbname="test_db",
                user="test_user",
                password="test_pass",
                output_path=backup_path
            )
            
            assert success is True
            assert error == ""
            assert metadata["backup_tool"] == "pg_dump"
            
            # pg_dump 명령어 호출 검증
            mock_subprocess.assert_called_once()
            call_args = mock_subprocess.call_args[0][0]
            assert "pg_dump" in call_args
    
    @patch('subprocess.run')
    def test_mysql_backup_scenario_mock(self, mock_subprocess):
        """MySQL 백업 시나리오 테스트 (모킹)"""
        # subprocess.run 모킹
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "mysqldump completed successfully"
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result
        
        adapter = create_backup_adapter("mysql", "test_mysql_e2e")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_path = Path(temp_dir) / "backup.sql"
            
            # 백업 파일 생성 (모킹을 위해)
            backup_path.write_text("-- MySQL dump\nCREATE TABLE test();")
            
            success, error, metadata = adapter.run_backup(
                host="localhost",
                port=3306,
                dbname="test_db",
                user="test_user",
                password="test_pass",
                output_path=backup_path
            )
            
            assert success is True
            assert error == ""
            assert metadata["backup_tool"] == "mysqldump"
            
            # mysqldump 명령어 호출 검증
            mock_subprocess.assert_called_once()
            call_args = mock_subprocess.call_args[0][0]
            assert "mysqldump" in call_args


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
