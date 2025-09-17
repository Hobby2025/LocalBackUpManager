"""
백업 엔진 단위 테스트
"""

import pytest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock
from datetime import datetime

from app.core.backup_engine import BackupEngine
from app.database import Database, Backup


@pytest.mark.unit
class TestBackupEngine:
    """백업 엔진 테스트"""
    
    @pytest.fixture
    def backup_engine(self):
        """백업 엔진 인스턴스"""
        return BackupEngine()
    
    @pytest.fixture
    def sample_database(self, test_db, database_factory):
        """테스트용 데이터베이스"""
        return database_factory.create(
            test_db,
            name="test_backup_db",
            host="localhost",
            port=5432,
            database_name="testdb",
            username="testuser",
            password_encrypted="testpass"
        )
    
    @pytest.fixture
    def temp_backup_dir(self):
        """임시 백업 디렉토리"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_backup_engine_initialization(self, backup_engine):
        """백업 엔진 초기화 테스트"""
        assert backup_engine is not None
        assert hasattr(backup_engine, 'create_backup')
        assert hasattr(backup_engine, 'compress_file')
        assert hasattr(backup_engine, 'encrypt_file')
        assert hasattr(backup_engine, 'calculate_checksum')
    
    @patch('subprocess.run')
    def test_pg_dump_execution_success(self, mock_subprocess, backup_engine, sample_database, temp_backup_dir):
        """pg_dump 실행 성공 테스트"""
        # Mock subprocess.run 성공 응답
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.stdout = b"-- PostgreSQL database dump\nCREATE TABLE test();"
        mock_process.stderr = b""
        mock_subprocess.return_value = mock_process
        
        # Mock pg_dump 버전 확인
        with patch('subprocess.check_output') as mock_version:
            mock_version.return_value = b"pg_dump (PostgreSQL) 14.0\n"
            
            backup_file = temp_backup_dir / "test_backup.sql"
            result = backup_engine._execute_pg_dump(
                sample_database,
                str(backup_file),
                backup_type="full"
            )
        
        assert result["success"] is True
        assert result["pg_dump_version"] == "14.0"
        assert "duration_seconds" in result
        
        # pg_dump 명령어가 올바르게 호출되었는지 확인
        mock_subprocess.assert_called_once()
        call_args = mock_subprocess.call_args[0][0]
        assert "pg_dump" in call_args
        assert "--host=localhost" in call_args
        assert "--port=5432" in call_args
        assert "--username=testuser" in call_args
        assert "--dbname=testdb" in call_args
    
    @patch('subprocess.run')
    def test_pg_dump_execution_failure(self, mock_subprocess, backup_engine, sample_database, temp_backup_dir):
        """pg_dump 실행 실패 테스트"""
        # Mock subprocess.run 실패 응답
        mock_process = Mock()
        mock_process.returncode = 1
        mock_process.stdout = b""
        mock_process.stderr = b"pg_dump: error: connection to database failed"
        mock_subprocess.return_value = mock_process
        
        backup_file = temp_backup_dir / "test_backup.sql"
        result = backup_engine._execute_pg_dump(
            sample_database,
            str(backup_file),
            backup_type="full"
        )
        
        assert result["success"] is False
        assert "connection to database failed" in result["error_message"]
    
    def test_file_compression_gzip(self, backup_engine, temp_backup_dir):
        """gzip 압축 테스트"""
        # 테스트 파일 생성
        test_file = temp_backup_dir / "test.sql"
        test_content = "CREATE TABLE test(id INTEGER);\nINSERT INTO test VALUES (1);"
        test_file.write_text(test_content)
        
        # 압축 실행
        compressed_file = backup_engine.compress_file(str(test_file), algorithm="gzip")
        
        assert compressed_file.endswith(".gz")
        assert Path(compressed_file).exists()
        assert Path(compressed_file).stat().st_size > 0
        
        # 압축률 확인
        original_size = test_file.stat().st_size
        compressed_size = Path(compressed_file).stat().st_size
        assert compressed_size < original_size
    
    def test_file_compression_unsupported_algorithm(self, backup_engine, temp_backup_dir):
        """지원하지 않는 압축 알고리즘 테스트"""
        test_file = temp_backup_dir / "test.sql"
        test_file.write_text("test content")
        
        with pytest.raises(ValueError, match="지원하지 않는 압축 알고리즘"):
            backup_engine.compress_file(str(test_file), algorithm="unsupported")
    
    @patch('app.core.backup_engine.get_encryption_key')
    def test_file_encryption(self, mock_get_key, backup_engine, temp_backup_dir):
        """파일 암호화 테스트"""
        # Mock 암호화 키
        mock_get_key.return_value = b"a" * 32  # 32바이트 키
        
        # 테스트 파일 생성
        test_file = temp_backup_dir / "test.sql.gz"
        test_content = b"compressed backup data"
        test_file.write_bytes(test_content)
        
        # 암호화 실행
        encrypted_file = backup_engine.encrypt_file(str(test_file))
        
        assert encrypted_file.endswith(".enc")
        assert Path(encrypted_file).exists()
        
        # 암호화된 파일이 원본과 다른지 확인
        encrypted_content = Path(encrypted_file).read_bytes()
        assert encrypted_content != test_content
        assert len(encrypted_content) > len(test_content)  # 헤더 정보 포함
    
    def test_checksum_calculation(self, backup_engine, temp_backup_dir):
        """체크섬 계산 테스트"""
        # 테스트 파일 생성
        test_file = temp_backup_dir / "test.sql"
        test_content = "test backup content"
        test_file.write_text(test_content)
        
        # 체크섬 계산
        checksum = backup_engine.calculate_checksum(str(test_file))
        
        assert checksum is not None
        assert len(checksum) == 64  # SHA-256 해시는 64자
        assert isinstance(checksum, str)
        
        # 같은 파일의 체크섬은 항상 동일해야 함
        checksum2 = backup_engine.calculate_checksum(str(test_file))
        assert checksum == checksum2
    
    def test_checksum_different_files(self, backup_engine, temp_backup_dir):
        """다른 파일의 체크섬은 달라야 함"""
        file1 = temp_backup_dir / "test1.sql"
        file2 = temp_backup_dir / "test2.sql"
        
        file1.write_text("content 1")
        file2.write_text("content 2")
        
        checksum1 = backup_engine.calculate_checksum(str(file1))
        checksum2 = backup_engine.calculate_checksum(str(file2))
        
        assert checksum1 != checksum2
    
    @patch('app.core.backup_engine.BackupEngine._execute_pg_dump')
    @patch('app.core.backup_engine.get_encryption_key')
    def test_create_backup_full_process(self, mock_get_key, mock_pg_dump, backup_engine, test_db, sample_database, temp_backup_dir):
        """전체 백업 프로세스 테스트"""
        # Mock 설정
        mock_get_key.return_value = b"a" * 32
        mock_pg_dump.return_value = {
            "success": True,
            "pg_dump_version": "14.0",
            "duration_seconds": 5
        }
        
        # 임시 SQL 파일 생성 (pg_dump 결과 시뮬레이션)
        sql_file = temp_backup_dir / "backup.sql"
        sql_file.write_text("-- PostgreSQL database dump\nCREATE TABLE test();")
        
        # 백업 실행
        with patch('app.core.backup_engine.BackupEngine._get_backup_file_path') as mock_path:
            mock_path.return_value = str(sql_file)
            
            result = backup_engine.create_backup(
                db_session=test_db,
                database=sample_database,
                backup_type="full"
            )
        
        assert result["success"] is True
        assert "backup_id" in result
        assert result["backup_type"] == "full"
        assert result["pg_dump_version"] == "14.0"
        
        # 백업 레코드가 데이터베이스에 생성되었는지 확인
        backup_record = test_db.query(Backup).filter(Backup.id == result["backup_id"]).first()
        assert backup_record is not None
        assert backup_record.status == "completed"
        assert backup_record.backup_type == "full"
        assert backup_record.is_encrypted is True
        assert backup_record.checksum is not None
    
    @patch('app.core.backup_engine.BackupEngine._execute_pg_dump')
    def test_create_backup_pg_dump_failure(self, mock_pg_dump, backup_engine, test_db, sample_database):
        """pg_dump 실패 시 백업 프로세스 테스트"""
        # Mock pg_dump 실패
        mock_pg_dump.return_value = {
            "success": False,
            "error_message": "Connection failed"
        }
        
        result = backup_engine.create_backup(
            db_session=test_db,
            database=sample_database,
            backup_type="full"
        )
        
        assert result["success"] is False
        assert "Connection failed" in result["error_message"]
        
        # 실패한 백업 레코드가 생성되었는지 확인
        backup_record = test_db.query(Backup).filter(Backup.id == result["backup_id"]).first()
        assert backup_record is not None
        assert backup_record.status == "failed"
        assert backup_record.error_message == "Connection failed"
    
    def test_get_backup_file_path(self, backup_engine):
        """백업 파일 경로 생성 테스트"""
        database_name = "test_db"
        backup_type = "full"
        
        file_path = backup_engine._get_backup_file_path(database_name, backup_type)
        
        assert database_name in file_path
        assert backup_type in file_path
        assert file_path.endswith(".sql")
        assert "data/backups" in file_path
        
        # 날짜가 포함되어 있는지 확인
        today = datetime.now().strftime("%Y%m%d")
        assert today in file_path
    
    def test_backup_metadata_update(self, backup_engine, test_db, sample_database, temp_backup_dir):
        """백업 메타데이터 업데이트 테스트"""
        # 테스트 백업 레코드 생성
        backup_record = Backup(
            database_id=sample_database.id,
            backup_type="full",
            status="running"
        )
        test_db.add(backup_record)
        test_db.commit()
        test_db.refresh(backup_record)
        
        # 테스트 파일 생성
        test_file = temp_backup_dir / "backup.sql.gz.enc"
        test_file.write_bytes(b"encrypted backup data")
        
        # 메타데이터 업데이트
        backup_engine._update_backup_metadata(
            db_session=test_db,
            backup_record=backup_record,
            file_path=str(test_file),
            checksum="abc123def456",
            pg_dump_version="14.0",
            duration_seconds=10,
            original_size=2048,
            compressed_size=1024
        )
        
        test_db.refresh(backup_record)
        
        assert backup_record.status == "completed"
        assert backup_record.file_path == str(test_file)
        assert backup_record.checksum == "abc123def456"
        assert backup_record.pg_dump_version == "14.0"
        assert backup_record.duration_seconds == 10
        assert backup_record.file_size == 2048
        assert backup_record.compressed_size == 1024
        assert backup_record.compression_ratio == 0.5
        assert backup_record.is_encrypted is True
        assert backup_record.completed_at is not None
    
    def test_backup_directory_creation(self, backup_engine, temp_backup_dir):
        """백업 디렉토리 자동 생성 테스트"""
        # 존재하지 않는 디렉토리 경로
        non_existent_dir = temp_backup_dir / "new_backup_dir"
        backup_file = non_existent_dir / "backup.sql"
        
        # 디렉토리가 자동 생성되는지 확인
        backup_engine._ensure_backup_directory(str(backup_file))
        
        assert non_existent_dir.exists()
        assert non_existent_dir.is_dir()
    
    @patch('shutil.which')
    def test_pg_dump_availability_check(self, mock_which, backup_engine):
        """pg_dump 사용 가능성 확인 테스트"""
        # pg_dump가 사용 가능한 경우
        mock_which.return_value = "/usr/bin/pg_dump"
        assert backup_engine._check_pg_dump_available() is True
        
        # pg_dump가 사용 불가능한 경우
        mock_which.return_value = None
        assert backup_engine._check_pg_dump_available() is False
    
    def test_backup_type_validation(self, backup_engine):
        """백업 타입 검증 테스트"""
        valid_types = ["full", "incremental", "schema", "data"]
        
        for backup_type in valid_types:
            assert backup_engine._validate_backup_type(backup_type) is True
        
        invalid_types = ["invalid", "partial", ""]
        
        for backup_type in invalid_types:
            assert backup_engine._validate_backup_type(backup_type) is False
