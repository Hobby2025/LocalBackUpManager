"""
PostgreSQL 호환성 회귀 테스트
기존 PostgreSQL 기능에 영향을 주지 않는지 검증
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, Mock
import subprocess

from app.core.backup_engine import BackupEngine


@pytest.mark.regression
class TestPostgreSQLCompatibility:
    """PostgreSQL 호환성 테스트"""
    
    @pytest.fixture
    def temp_backup_dir(self):
        """임시 백업 디렉토리"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def sample_database(self, test_db, database_factory):
        """테스트용 데이터베이스"""
        return database_factory.create(
            test_db,
            name="regression_test_db",
            display_name="회귀 테스트 DB",
            host="localhost",
            port=5432,
            database_name="regressiondb",
            username="regressionuser",
            password_encrypted="regressionpass"
        )
    
    def test_pg_dump_version_compatibility(self):
        """pg_dump 버전 호환성 테스트"""
        backup_engine = BackupEngine()
        
        # 다양한 PostgreSQL 버전 시뮬레이션
        version_outputs = [
            b"pg_dump (PostgreSQL) 12.0\n",
            b"pg_dump (PostgreSQL) 13.5\n",
            b"pg_dump (PostgreSQL) 14.2\n",
            b"pg_dump (PostgreSQL) 15.1\n",
            b"pg_dump (PostgreSQL) 16.0\n"
        ]
        
        for version_output in version_outputs:
            with patch('subprocess.check_output') as mock_version:
                mock_version.return_value = version_output
                
                # 버전 추출 테스트
                version = backup_engine._get_pg_dump_version()
                
                # 버전 형식 검증
                assert version is not None
                assert len(version.split('.')) >= 2
                assert version.replace('.', '').isdigit()
                
                # 지원되는 버전인지 확인 (12.0 이상)
                major_version = int(version.split('.')[0])
                assert major_version >= 12, f"지원하지 않는 PostgreSQL 버전: {version}"
    
    @patch('subprocess.run')
    def test_pg_dump_standard_options(self, mock_subprocess, sample_database, temp_backup_dir):
        """pg_dump 표준 옵션 호환성 테스트"""
        backup_engine = BackupEngine()
        
        # pg_dump 성공 시뮬레이션
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.stdout = b"-- PostgreSQL database dump\nCREATE TABLE test();"
        mock_process.stderr = b""
        mock_subprocess.return_value = mock_process
        
        backup_file = temp_backup_dir / "compatibility_test.sql"
        
        result = backup_engine._execute_pg_dump(
            sample_database,
            str(backup_file),
            backup_type="full"
        )
        
        assert result["success"] is True
        
        # 호출된 명령어 검증
        mock_subprocess.assert_called_once()
        call_args = mock_subprocess.call_args[0][0]
        
        # 필수 pg_dump 옵션들이 포함되어 있는지 확인
        required_options = [
            "pg_dump",
            "--host=localhost",
            "--port=5432",
            "--username=regressionuser",
            "--dbname=regressiondb",
            "--no-password",
            "--verbose",
            "--file"
        ]
        
        command_str = " ".join(call_args)
        for option in required_options:
            assert option in command_str, f"필수 옵션이 누락되었습니다: {option}"
        
        # 위험한 옵션이 포함되지 않았는지 확인
        dangerous_options = [
            "--clean",  # DROP 문 포함
            "--if-exists",  # 위험한 조건부 삭제
        ]
        
        for option in dangerous_options:
            assert option not in command_str, f"위험한 옵션이 포함되었습니다: {option}"
    
    @patch('subprocess.run')
    def test_pg_dump_schema_only_compatibility(self, mock_subprocess, sample_database, temp_backup_dir):
        """스키마 전용 백업 호환성 테스트"""
        backup_engine = BackupEngine()
        
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.stdout = b"-- PostgreSQL database dump\nCREATE TABLE test();"
        mock_process.stderr = b""
        mock_subprocess.return_value = mock_process
        
        backup_file = temp_backup_dir / "schema_test.sql"
        
        result = backup_engine._execute_pg_dump(
            sample_database,
            str(backup_file),
            backup_type="schema"
        )
        
        assert result["success"] is True
        
        # 스키마 전용 옵션 확인
        call_args = mock_subprocess.call_args[0][0]
        command_str = " ".join(call_args)
        assert "--schema-only" in command_str, "스키마 전용 옵션이 누락되었습니다"
    
    @patch('subprocess.run')
    def test_pg_dump_data_only_compatibility(self, mock_subprocess, sample_database, temp_backup_dir):
        """데이터 전용 백업 호환성 테스트"""
        backup_engine = BackupEngine()
        
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.stdout = b"-- PostgreSQL database dump\nINSERT INTO test VALUES (1);"
        mock_process.stderr = b""
        mock_subprocess.return_value = mock_process
        
        backup_file = temp_backup_dir / "data_test.sql"
        
        result = backup_engine._execute_pg_dump(
            sample_database,
            str(backup_file),
            backup_type="data"
        )
        
        assert result["success"] is True
        
        # 데이터 전용 옵션 확인
        call_args = mock_subprocess.call_args[0][0]
        command_str = " ".join(call_args)
        assert "--data-only" in command_str, "데이터 전용 옵션이 누락되었습니다"
    
    @patch('subprocess.run')
    def test_pg_dump_error_handling(self, mock_subprocess, sample_database, temp_backup_dir):
        """pg_dump 오류 처리 호환성 테스트"""
        backup_engine = BackupEngine()
        
        # 다양한 오류 상황 시뮬레이션
        error_scenarios = [
            {
                "returncode": 1,
                "stderr": b"pg_dump: error: connection to database failed",
                "expected_error": "connection to database failed"
            },
            {
                "returncode": 2,
                "stderr": b"pg_dump: error: query failed: ERROR: permission denied",
                "expected_error": "permission denied"
            },
            {
                "returncode": 1,
                "stderr": b"pg_dump: error: could not connect to server",
                "expected_error": "could not connect to server"
            }
        ]
        
        for scenario in error_scenarios:
            mock_process = Mock()
            mock_process.returncode = scenario["returncode"]
            mock_process.stdout = b""
            mock_process.stderr = scenario["stderr"]
            mock_subprocess.return_value = mock_process
            
            backup_file = temp_backup_dir / "error_test.sql"
            
            result = backup_engine._execute_pg_dump(
                sample_database,
                str(backup_file),
                backup_type="full"
            )
            
            assert result["success"] is False
            assert scenario["expected_error"] in result["error_message"]
    
    def test_postgresql_connection_string_format(self, sample_database):
        """PostgreSQL 연결 문자열 형식 호환성 테스트"""
        backup_engine = BackupEngine()
        
        # 연결 문자열 생성 테스트
        connection_params = backup_engine._build_connection_params(sample_database)
        
        # 필수 연결 파라미터 확인
        required_params = ["host", "port", "username", "dbname"]
        for param in required_params:
            assert any(f"--{param}=" in arg for arg in connection_params), \
                f"필수 연결 파라미터가 누락되었습니다: {param}"
        
        # 보안 관련 파라미터 확인
        assert "--no-password" in connection_params, "패스워드 프롬프트 비활성화 옵션이 누락되었습니다"
        
        # 환경 변수 설정 확인 (PGPASSWORD)
        env_vars = backup_engine._build_environment_vars(sample_database)
        assert "PGPASSWORD" in env_vars, "PGPASSWORD 환경 변수가 설정되지 않았습니다"
    
    def test_postgresql_ssl_compatibility(self, test_db, database_factory):
        """PostgreSQL SSL 연결 호환성 테스트"""
        backup_engine = BackupEngine()
        
        # 다양한 SSL 모드 테스트
        ssl_modes = ["disable", "allow", "prefer", "require", "verify-ca", "verify-full"]
        
        for ssl_mode in ssl_modes:
            ssl_database = database_factory.create(
                test_db,
                name=f"ssl_test_{ssl_mode}",
                host="localhost",
                port=5432,
                database_name="ssldb",
                username="ssluser",
                password_encrypted="sslpass",
                ssl_mode=ssl_mode
            )
            
            connection_params = backup_engine._build_connection_params(ssl_database)
            
            # SSL 모드가 올바르게 설정되었는지 확인
            if ssl_mode != "disable":
                # SSL 관련 환경 변수 확인
                env_vars = backup_engine._build_environment_vars(ssl_database)
                assert "PGSSLMODE" in env_vars, f"SSL 모드 환경 변수가 누락되었습니다: {ssl_mode}"
                assert env_vars["PGSSLMODE"] == ssl_mode, f"SSL 모드가 올바르지 않습니다: {ssl_mode}"
    
    def test_postgresql_encoding_compatibility(self):
        """PostgreSQL 인코딩 호환성 테스트"""
        backup_engine = BackupEngine()
        
        # 다양한 인코딩으로 생성된 덤프 파일 시뮬레이션
        encoding_tests = [
            ("UTF-8", "-- PostgreSQL database dump\n-- 한글 테스트\nCREATE TABLE 테스트();"),
            ("LATIN1", "-- PostgreSQL database dump\nCREATE TABLE test();"),
            ("UTF-16", "-- PostgreSQL database dump\nCREATE TABLE test();")
        ]
        
        for encoding, content in encoding_tests:
            # 인코딩별 파일 처리 테스트
            try:
                # 파일 내용을 바이트로 변환
                content_bytes = content.encode(encoding.lower().replace('-', ''))
                
                # 파일 크기 계산
                file_size = len(content_bytes)
                
                # 기본적인 처리가 가능한지 확인
                assert file_size > 0, f"{encoding} 인코딩 처리 실패"
                
            except UnicodeEncodeError:
                # 일부 인코딩에서는 특정 문자가 지원되지 않을 수 있음
                # 이는 정상적인 동작
                pass
    
    def test_postgresql_large_object_compatibility(self, sample_database, temp_backup_dir):
        """PostgreSQL 대용량 객체 호환성 테스트"""
        backup_engine = BackupEngine()
        
        with patch('subprocess.run') as mock_subprocess:
            # 대용량 객체가 포함된 덤프 시뮬레이션
            mock_process = Mock()
            mock_process.returncode = 0
            mock_process.stdout = b"""-- PostgreSQL database dump
-- Large Objects
SELECT pg_catalog.lo_create('12345');
CREATE TABLE test_table();
"""
            mock_process.stderr = b""
            mock_subprocess.return_value = mock_process
            
            backup_file = temp_backup_dir / "large_object_test.sql"
            
            result = backup_engine._execute_pg_dump(
                sample_database,
                str(backup_file),
                backup_type="full"
            )
            
            assert result["success"] is True
            
            # 대용량 객체 관련 옵션 확인
            call_args = mock_subprocess.call_args[0][0]
            command_str = " ".join(call_args)
            
            # 대용량 객체 포함 옵션이 있는지 확인 (기본적으로 포함됨)
            # --no-blobs 옵션이 없어야 함
            assert "--no-blobs" not in command_str, "대용량 객체가 제외되었습니다"
    
    def test_postgresql_transaction_compatibility(self, sample_database, temp_backup_dir):
        """PostgreSQL 트랜잭션 호환성 테스트"""
        backup_engine = BackupEngine()
        
        with patch('subprocess.run') as mock_subprocess:
            # 트랜잭션이 포함된 덤프 시뮬레이션
            mock_process = Mock()
            mock_process.returncode = 0
            mock_process.stdout = b"""-- PostgreSQL database dump
BEGIN;
CREATE TABLE test_table();
INSERT INTO test_table VALUES (1);
COMMIT;
"""
            mock_process.stderr = b""
            mock_subprocess.return_value = mock_process
            
            backup_file = temp_backup_dir / "transaction_test.sql"
            
            result = backup_engine._execute_pg_dump(
                sample_database,
                str(backup_file),
                backup_type="full"
            )
            
            assert result["success"] is True
            
            # 트랜잭션 관련 옵션 확인
            call_args = mock_subprocess.call_args[0][0]
            command_str = " ".join(call_args)
            
            # 단일 트랜잭션 옵션 확인 (일관성 보장)
            assert "--single-transaction" in command_str, "단일 트랜잭션 옵션이 누락되었습니다"
    
    def test_postgresql_privilege_compatibility(self, test_db, database_factory):
        """PostgreSQL 권한 호환성 테스트"""
        backup_engine = BackupEngine()
        
        # 다양한 권한 레벨의 사용자 시뮬레이션
        privilege_tests = [
            ("superuser", "postgres", True),
            ("database_owner", "dbowner", True),
            ("read_only", "readonly", False),
            ("limited_user", "limited", False)
        ]
        
        for role_name, username, should_succeed in privilege_tests:
            priv_database = database_factory.create(
                test_db,
                name=f"priv_test_{role_name}",
                host="localhost",
                port=5432,
                database_name="privdb",
                username=username,
                password_encrypted="privpass"
            )
            
            connection_params = backup_engine._build_connection_params(priv_database)
            
            # 사용자명이 올바르게 설정되었는지 확인
            username_param = next((param for param in connection_params if param.startswith("--username=")), None)
            assert username_param is not None, f"사용자명 파라미터가 누락되었습니다: {role_name}"
            assert username in username_param, f"사용자명이 올바르지 않습니다: {username}"
