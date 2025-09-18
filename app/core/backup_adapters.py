"""
백업 어댑터 패턴 구현
- 다중 DB 타입 지원 (PostgreSQL, MySQL, SQLite)
- 통일된 인터페이스로 백업 기능 제공
- 각 DB별 최적화된 백업 전략 구현

주의:
- 변수명은 기존 코드와 충돌하지 않도록 새로운 범위에서만 정의
- 외부 의존성 추가 금지 (requirements.txt 내 패키지만 사용)
- Windows/Unix 환경 모두 동작
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import tempfile
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple, Any

from app.config import get_config_manager


class BackupAdapter(ABC):
    """백업 어댑터 인터페이스
    
    모든 DB 타입에 대해 통일된 백업 인터페이스를 제공합니다.
    """
    
    def __init__(self, database_id: str) -> None:
        self.database_id = database_id
    
    @abstractmethod
    def run_backup(
        self,
        *,
        host: str,
        port: int,
        dbname: str,
        user: str,
        password: Optional[str],
        output_path: Path,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """백업을 실행합니다.
        
        Args:
            host: 데이터베이스 호스트
            port: 데이터베이스 포트
            dbname: 데이터베이스 이름
            user: 사용자명
            password: 비밀번호
            output_path: 백업 파일 출력 경로
            options: 백업 옵션 (DB별로 다름)
        
        Returns:
            Tuple[bool, str, Dict[str, Any]]: (성공여부, 오류메시지, 메타데이터)
        """
        pass
    
    @abstractmethod
    def get_backup_command(
        self,
        *,
        host: str,
        port: int,
        dbname: str,
        user: str,
        password: Optional[str],
        output_path: Path,
        options: Optional[Dict[str, Any]] = None,
    ) -> list[str]:
        """백업 명령어를 생성합니다."""
        pass
    
    @abstractmethod
    def validate_options(self, options: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """백업 옵션을 검증하고 기본값을 설정합니다."""
        pass


class PostgresBackupAdapter(BackupAdapter):
    """PostgreSQL 백업 어댑터 (pg_dump 기반)"""
    
    def __init__(self, database_id: str) -> None:
        super().__init__(database_id)
    
    def validate_options(self, options: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """PostgreSQL 백업 옵션 검증 및 기본값 설정"""
        validated = {
            "format": "custom",  # custom, plain, directory, tar
            "compress": 6,       # 0-9 압축 레벨
            "verbose": True,     # 상세 출력
            "no_owner": True,    # 소유자 정보 제외
            "no_privileges": False,  # 권한 정보 포함
            "schema_only": False,    # 스키마만 백업
            "data_only": False,      # 데이터만 백업
            "exclude_tables": [],    # 제외할 테이블 목록
            "include_tables": [],    # 포함할 테이블 목록 (비어있으면 전체)
        }
        
        if options:
            for key, value in options.items():
                if key in validated:
                    validated[key] = value
        
        return validated
    
    def get_backup_command(
        self,
        *,
        host: str,
        port: int,
        dbname: str,
        user: str,
        password: Optional[str],
        output_path: Path,
        options: Optional[Dict[str, Any]] = None,
    ) -> list[str]:
        """pg_dump 명령어 생성"""
        opts = self.validate_options(options)
        
        cmd = [
            "pg_dump",
            f"--host={host}",
            f"--port={port}",
            f"--username={user}",
            f"--dbname={dbname}",
            f"--format={opts['format']}",
            f"--file={output_path}",
        ]
        
        # 압축 설정
        if opts["compress"] > 0:
            cmd.append(f"--compress={opts['compress']}")
        
        # 기타 옵션
        if opts["verbose"]:
            cmd.append("--verbose")
        if opts["no_owner"]:
            cmd.append("--no-owner")
        if opts["no_privileges"]:
            cmd.append("--no-privileges")
        if opts["schema_only"]:
            cmd.append("--schema-only")
        if opts["data_only"]:
            cmd.append("--data-only")
        
        # 테이블 제외/포함
        for table in opts["exclude_tables"]:
            cmd.extend(["--exclude-table", table])
        for table in opts["include_tables"]:
            cmd.extend(["--table", table])
        
        return cmd
    
    def run_backup(
        self,
        *,
        host: str,
        port: int,
        dbname: str,
        user: str,
        password: Optional[str],
        output_path: Path,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """PostgreSQL 백업 실행"""
        try:
            # 출력 디렉터리 생성
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 백업 명령어 생성
            cmd = self.get_backup_command(
                host=host, port=port, dbname=dbname,
                user=user, password=password, output_path=output_path,
                options=options
            )
            
            # 환경변수 설정 (비밀번호)
            env = os.environ.copy()
            if password:
                env["PGPASSWORD"] = password
            
            # 백업 실행
            start_time = datetime.utcnow()
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=3600  # 1시간 타임아웃
            )
            end_time = datetime.utcnow()
            
            # 결과 처리
            if result.returncode == 0:
                file_size = output_path.stat().st_size if output_path.exists() else 0
                metadata = {
                    "duration_seconds": int((end_time - start_time).total_seconds()),
                    "file_size_bytes": file_size,
                    "backup_tool": "pg_dump",
                    "backup_format": self.validate_options(options)["format"],
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
                return True, "", metadata
            else:
                error_msg = f"pg_dump 실패 (코드: {result.returncode}): {result.stderr}"
                metadata = {
                    "duration_seconds": int((end_time - start_time).total_seconds()),
                    "backup_tool": "pg_dump",
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "return_code": result.returncode,
                }
                return False, error_msg, metadata
                
        except subprocess.TimeoutExpired:
            return False, "백업 시간 초과 (1시간)", {"backup_tool": "pg_dump"}
        except Exception as e:
            return False, f"백업 실행 오류: {str(e)}", {"backup_tool": "pg_dump"}


class MySQLBackupAdapter(BackupAdapter):
    """MySQL 백업 어댑터 (mysqldump 기반)"""
    
    def __init__(self, database_id: str) -> None:
        super().__init__(database_id)
    
    def validate_options(self, options: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """MySQL 백업 옵션 검증 및 기본값 설정"""
        validated = {
            "single_transaction": True,   # 단일 트랜잭션으로 일관성 보장
            "routines": True,            # 저장 프로시저/함수 포함
            "triggers": True,            # 트리거 포함
            "events": True,              # 이벤트 포함
            "add_drop_table": True,      # DROP TABLE 문 추가
            "add_locks": True,           # LOCK TABLES 문 추가
            "disable_keys": True,        # 키 비활성화로 성능 향상
            "extended_insert": True,     # 확장 INSERT 문 사용
            "compress": False,           # mysqldump 자체 압축 (별도 gzip 사용)
            "exclude_tables": [],        # 제외할 테이블 목록
            "include_tables": [],        # 포함할 테이블 목록
            "where_clause": "",          # WHERE 조건절
        }
        
        if options:
            for key, value in options.items():
                if key in validated:
                    validated[key] = value
        
        return validated
    
    def get_backup_command(
        self,
        *,
        host: str,
        port: int,
        dbname: str,
        user: str,
        password: Optional[str],
        output_path: Path,
        options: Optional[Dict[str, Any]] = None,
    ) -> list[str]:
        """mysqldump 명령어 생성"""
        opts = self.validate_options(options)
        
        cmd = [
            "mysqldump",
            f"--host={host}",
            f"--port={port}",
            f"--user={user}",
            "--result-file=" + str(output_path),
        ]
        
        # 비밀번호 설정
        if password:
            cmd.append(f"--password={password}")
        
        # 기본 옵션들
        if opts["single_transaction"]:
            cmd.append("--single-transaction")
        if opts["routines"]:
            cmd.append("--routines")
        if opts["triggers"]:
            cmd.append("--triggers")
        if opts["events"]:
            cmd.append("--events")
        if opts["add_drop_table"]:
            cmd.append("--add-drop-table")
        if opts["add_locks"]:
            cmd.append("--add-locks")
        if opts["disable_keys"]:
            cmd.append("--disable-keys")
        if opts["extended_insert"]:
            cmd.append("--extended-insert")
        if opts["compress"]:
            cmd.append("--compress")
        
        # WHERE 조건절
        if opts["where_clause"]:
            cmd.extend(["--where", opts["where_clause"]])
        
        # 테이블 제외/포함
        for table in opts["exclude_tables"]:
            cmd.extend(["--ignore-table", f"{dbname}.{table}"])
        
        # 포함할 테이블이 지정된 경우
        if opts["include_tables"]:
            cmd.append(dbname)
            cmd.extend(opts["include_tables"])
        else:
            cmd.append(dbname)
        
        return cmd
    
    def run_backup(
        self,
        *,
        host: str,
        port: int,
        dbname: str,
        user: str,
        password: Optional[str],
        output_path: Path,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """MySQL 백업 실행"""
        try:
            # 출력 디렉터리 생성
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 백업 명령어 생성
            cmd = self.get_backup_command(
                host=host, port=port, dbname=dbname,
                user=user, password=password, output_path=output_path,
                options=options
            )
            
            # 백업 실행
            start_time = datetime.utcnow()
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600  # 1시간 타임아웃
            )
            end_time = datetime.utcnow()
            
            # 결과 처리
            if result.returncode == 0:
                file_size = output_path.stat().st_size if output_path.exists() else 0
                metadata = {
                    "duration_seconds": int((end_time - start_time).total_seconds()),
                    "file_size_bytes": file_size,
                    "backup_tool": "mysqldump",
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
                return True, "", metadata
            else:
                error_msg = f"mysqldump 실패 (코드: {result.returncode}): {result.stderr}"
                metadata = {
                    "duration_seconds": int((end_time - start_time).total_seconds()),
                    "backup_tool": "mysqldump",
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "return_code": result.returncode,
                }
                return False, error_msg, metadata
                
        except subprocess.TimeoutExpired:
            return False, "백업 시간 초과 (1시간)", {"backup_tool": "mysqldump"}
        except Exception as e:
            return False, f"백업 실행 오류: {str(e)}", {"backup_tool": "mysqldump"}


class SQLiteBackupAdapter(BackupAdapter):
    """SQLite 백업 어댑터 (파일 복사 및 sqlite3 backup API 기반)"""
    
    def __init__(self, database_id: str) -> None:
        super().__init__(database_id)
    
    def validate_options(self, options: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """SQLite 백업 옵션 검증 및 기본값 설정"""
        validated = {
            "method": "backup_api",  # backup_api, file_copy, dump
            "vacuum": True,          # 백업 전 VACUUM 실행
            "wal_checkpoint": True,  # WAL 체크포인트 실행
            "verify_integrity": True, # 무결성 검사
        }
        
        if options:
            for key, value in options.items():
                if key in validated:
                    validated[key] = value
        
        return validated
    
    def get_backup_command(
        self,
        *,
        host: str,
        port: int,
        dbname: str,
        user: str,
        password: Optional[str],
        output_path: Path,
        options: Optional[Dict[str, Any]] = None,
    ) -> list[str]:
        """SQLite는 명령어 기반이 아니므로 빈 리스트 반환"""
        return []
    
    def _backup_using_api(self, source_path: Path, output_path: Path, opts: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """sqlite3 backup API를 사용한 백업"""
        try:
            start_time = datetime.utcnow()
            
            # 소스 데이터베이스 연결
            source_conn = sqlite3.connect(str(source_path))
            
            try:
                # WAL 체크포인트 실행
                if opts["wal_checkpoint"]:
                    source_conn.execute("PRAGMA wal_checkpoint(FULL)")
                
                # VACUUM 실행 (옵션)
                if opts["vacuum"]:
                    source_conn.execute("VACUUM")
                
                # 무결성 검사
                if opts["verify_integrity"]:
                    integrity_result = source_conn.execute("PRAGMA integrity_check").fetchone()
                    if integrity_result[0] != "ok":
                        return False, f"데이터베이스 무결성 검사 실패: {integrity_result[0]}", {}
                
                # 백업 실행
                backup_conn = sqlite3.connect(str(output_path))
                try:
                    source_conn.backup(backup_conn)
                finally:
                    backup_conn.close()
                
            finally:
                source_conn.close()
            
            end_time = datetime.utcnow()
            file_size = output_path.stat().st_size if output_path.exists() else 0
            
            metadata = {
                "duration_seconds": int((end_time - start_time).total_seconds()),
                "file_size_bytes": file_size,
                "backup_tool": "sqlite3_backup_api",
                "backup_method": "backup_api",
            }
            
            return True, "", metadata
            
        except Exception as e:
            return False, f"SQLite backup API 오류: {str(e)}", {"backup_tool": "sqlite3_backup_api"}
    
    def _backup_using_file_copy(self, source_path: Path, output_path: Path, opts: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """파일 복사를 사용한 백업"""
        try:
            start_time = datetime.utcnow()
            
            # WAL 파일이 있는 경우 체크포인트 실행
            if opts["wal_checkpoint"]:
                conn = sqlite3.connect(str(source_path))
                try:
                    conn.execute("PRAGMA wal_checkpoint(FULL)")
                finally:
                    conn.close()
            
            # 파일 복사
            shutil.copy2(source_path, output_path)
            
            end_time = datetime.utcnow()
            file_size = output_path.stat().st_size if output_path.exists() else 0
            
            metadata = {
                "duration_seconds": int((end_time - start_time).total_seconds()),
                "file_size_bytes": file_size,
                "backup_tool": "file_copy",
                "backup_method": "file_copy",
            }
            
            return True, "", metadata
            
        except Exception as e:
            return False, f"파일 복사 오류: {str(e)}", {"backup_tool": "file_copy"}
    
    def _backup_using_dump(self, source_path: Path, output_path: Path, opts: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """sqlite3 .dump 명령을 사용한 백업"""
        try:
            start_time = datetime.utcnow()
            
            # sqlite3 .dump 명령 실행
            cmd = ["sqlite3", str(source_path), ".dump"]
            
            with open(output_path, 'w', encoding='utf-8') as f:
                result = subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=3600
                )
            
            end_time = datetime.utcnow()
            
            if result.returncode == 0:
                file_size = output_path.stat().st_size if output_path.exists() else 0
                metadata = {
                    "duration_seconds": int((end_time - start_time).total_seconds()),
                    "file_size_bytes": file_size,
                    "backup_tool": "sqlite3_dump",
                    "backup_method": "dump",
                    "stderr": result.stderr,
                }
                return True, "", metadata
            else:
                error_msg = f"sqlite3 dump 실패 (코드: {result.returncode}): {result.stderr}"
                metadata = {
                    "duration_seconds": int((end_time - start_time).total_seconds()),
                    "backup_tool": "sqlite3_dump",
                    "stderr": result.stderr,
                    "return_code": result.returncode,
                }
                return False, error_msg, metadata
                
        except subprocess.TimeoutExpired:
            return False, "백업 시간 초과 (1시간)", {"backup_tool": "sqlite3_dump"}
        except Exception as e:
            return False, f"SQLite dump 오류: {str(e)}", {"backup_tool": "sqlite3_dump"}
    
    def run_backup(
        self,
        *,
        host: str,
        port: int,
        dbname: str,
        user: str,
        password: Optional[str],
        output_path: Path,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """SQLite 백업 실행"""
        try:
            # 출력 디렉터리 생성
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # SQLite는 파일 기반이므로 dbname을 파일 경로로 사용
            source_path = Path(dbname)
            if not source_path.exists():
                return False, f"SQLite 데이터베이스 파일을 찾을 수 없습니다: {dbname}", {}
            
            # 옵션 검증
            opts = self.validate_options(options)
            
            # 백업 방법에 따라 실행
            if opts["method"] == "backup_api":
                return self._backup_using_api(source_path, output_path, opts)
            elif opts["method"] == "file_copy":
                return self._backup_using_file_copy(source_path, output_path, opts)
            elif opts["method"] == "dump":
                return self._backup_using_dump(source_path, output_path, opts)
            else:
                return False, f"지원하지 않는 백업 방법: {opts['method']}", {}
                
        except Exception as e:
            return False, f"SQLite 백업 오류: {str(e)}", {"backup_tool": "sqlite"}


def create_backup_adapter(db_type: str, database_id: str) -> BackupAdapter:
    """DB 타입에 따른 백업 어댑터 팩토리 함수"""
    db_type = db_type.lower().strip()
    
    if db_type == "postgresql":
        return PostgresBackupAdapter(database_id)
    elif db_type == "mysql":
        return MySQLBackupAdapter(database_id)
    elif db_type == "sqlite":
        return SQLiteBackupAdapter(database_id)
    else:
        raise ValueError(f"지원하지 않는 데이터베이스 타입입니다: {db_type}")
