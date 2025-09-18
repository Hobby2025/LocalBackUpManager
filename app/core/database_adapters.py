"""
데이터베이스 어댑터 패턴 구현
- 다중 DB 타입 지원 (PostgreSQL, MySQL, SQLite)
- 통일된 인터페이스로 연결/풀/테스트 기능 제공
- 각 DB별 최적화된 구현체 제공

주의:
- 변수명은 기존 코드와 충돌하지 않도록 새로운 범위에서만 정의
- 외부 의존성 추가 금지 (requirements.txt 내 패키지만 사용)
- Windows/Unix 환경 모두 동작
"""

from __future__ import annotations

import sqlite3
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional, Tuple, Union

import psycopg2
from psycopg2.pool import SimpleConnectionPool
from app.config import get_config_manager

try:
    import pymysql
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False


class DatabaseAdapter(ABC):
    """데이터베이스 어댑터 인터페이스
    
    모든 DB 타입에 대해 통일된 인터페이스를 제공합니다.
    """
    
    def __init__(self, database_id: str) -> None:
        self.database_id = database_id
    
    @abstractmethod
    def create_pool(
        self,
        *,
        host: str,
        port: int,
        dbname: str,
        user: str,
        password: Optional[str],
        sslmode: Optional[str],
        minconn: int = 1,
        maxconn: int = 5,
    ) -> Any:
        """연결 풀을 생성합니다."""
        pass
    
    @abstractmethod
    def get_connection(self) -> Any:
        """연결 풀에서 연결을 가져옵니다."""
        pass
    
    @abstractmethod
    def put_connection(self, conn: Any) -> None:
        """연결을 연결 풀에 반환합니다."""
        pass
    
    @abstractmethod
    def close_pool(self) -> None:
        """연결 풀을 종료합니다."""
        pass
    
    @abstractmethod
    def test_connection(
        self,
        *,
        host: str,
        port: int,
        dbname: str,
        user: str,
        password: Optional[str],
        sslmode: Optional[str],
        timeout_seconds: int = 5,
    ) -> Tuple[bool, float, Optional[str]]:
        """DB 연결 테스트를 수행합니다.
        
        Returns:
            Tuple[bool, float, Optional[str]]: (성공여부, 응답시간(ms), 오류메시지)
        """
        pass


class PostgresAdapter(DatabaseAdapter):
    """PostgreSQL 어댑터 (psycopg2 기반)"""
    
    def __init__(self, database_id: str) -> None:
        super().__init__(database_id)
        self._pool: Optional[SimpleConnectionPool] = None
    
    def _make_conn_params(
        self, 
        *, 
        host: str, 
        port: int, 
        dbname: str, 
        user: str, 
        password: Optional[str], 
        sslmode: Optional[str]
    ) -> Dict[str, Any]:
        """psycopg2 연결 파라미터 구성"""
        params: Dict[str, Any] = {
            "host": host,
            "port": int(port) if port is not None else 5432,
            "dbname": dbname,
            "user": user,
            "connect_timeout": 5,
        }
        if password:
            params["password"] = password
        # sslmode가 지정되지 않았으면 설정의 기본값을 사용
        params["sslmode"] = sslmode or self._get_default_ssl_mode()
        return params
    
    def _get_default_ssl_mode(self) -> str:
        """설정 파일의 기본 SSL 모드 반환"""
        try:
            cm = get_config_manager()
            app_settings = cm.load_app_settings() or {}
            sec = (app_settings.get('security') or {})
            mode = str(sec.get('db_ssl_mode_default') or '').strip().lower()
            if mode in {"disable", "prefer", "require", "verify-ca", "verify-full"}:
                return mode
        except Exception:
            pass
        return "require"
    
    def create_pool(
        self,
        *,
        host: str,
        port: int,
        dbname: str,
        user: str,
        password: Optional[str],
        sslmode: Optional[str],
        minconn: int = 1,
        maxconn: int = 5,
    ) -> SimpleConnectionPool:
        """PostgreSQL 연결 풀 생성"""
        if self._pool is not None:
            return self._pool
        
        params = self._make_conn_params(
            host=host, port=port, dbname=dbname, 
            user=user, password=password, sslmode=sslmode
        )
        self._pool = SimpleConnectionPool(minconn, maxconn, **params)
        return self._pool
    
    def get_connection(self) -> psycopg2.extensions.connection:
        """연결 풀에서 연결 가져오기"""
        if self._pool is None:
            raise RuntimeError("연결 풀이 존재하지 않습니다. 먼저 create_pool을 호출하세요.")
        return self._pool.getconn()
    
    def put_connection(self, conn: psycopg2.extensions.connection) -> None:
        """연결을 연결 풀에 반환"""
        if self._pool is None:
            # 풀이 이미 제거된 경우 안전하게 종료만 시도
            try:
                conn.close()
            finally:
                return
        self._pool.putconn(conn)
    
    def close_pool(self) -> None:
        """연결 풀 종료"""
        if self._pool is not None:
            self._pool.closeall()
            self._pool = None
    
    def test_connection(
        self,
        *,
        host: str,
        port: int,
        dbname: str,
        user: str,
        password: Optional[str],
        sslmode: Optional[str],
        timeout_seconds: int = 5,
    ) -> Tuple[bool, float, Optional[str]]:
        """PostgreSQL 연결 테스트"""
        start = time.perf_counter()
        try:
            params = self._make_conn_params(
                host=host, port=port, dbname=dbname, 
                user=user, password=password, sslmode=sslmode
            )
            params["connect_timeout"] = timeout_seconds
            conn = psycopg2.connect(**params)
            try:
                cur = conn.cursor()
                cur.execute("SELECT 1")
                cur.fetchone()
                cur.close()
            finally:
                conn.close()
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            return True, elapsed_ms, None
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            return False, elapsed_ms, str(e)


class MySQLAdapter(DatabaseAdapter):
    """MySQL 어댑터 (PyMySQL 기반)"""
    
    def __init__(self, database_id: str) -> None:
        super().__init__(database_id)
        self._pool_config: Optional[Dict[str, Any]] = None
        self._connections: Dict[int, Any] = {}  # 간단한 연결 풀 구현
        self._max_connections = 5
        self._min_connections = 1
        
        if not MYSQL_AVAILABLE:
            raise RuntimeError("PyMySQL이 설치되지 않았습니다. pip install PyMySQL을 실행하세요.")
    
    def _make_conn_params(
        self, 
        *, 
        host: str, 
        port: int, 
        dbname: str, 
        user: str, 
        password: Optional[str], 
        sslmode: Optional[str]
    ) -> Dict[str, Any]:
        """PyMySQL 연결 파라미터 구성"""
        params: Dict[str, Any] = {
            "host": host,
            "port": int(port) if port is not None else 3306,
            "database": dbname,  # MySQL은 database 파라미터 사용
            "user": user,
            "connect_timeout": 5,
            "charset": "utf8mb4",
            "autocommit": True,
        }
        if password:
            params["password"] = password
        
        # SSL 설정 (sslmode를 MySQL SSL 설정으로 변환)
        if sslmode and sslmode != "disable":
            params["ssl"] = {"ssl_disabled": False}
            if sslmode in ["verify-ca", "verify-full"]:
                params["ssl"]["check_hostname"] = True
        else:
            params["ssl_disabled"] = True
        
        return params
    
    def create_pool(
        self,
        *,
        host: str,
        port: int,
        dbname: str,
        user: str,
        password: Optional[str],
        sslmode: Optional[str],
        minconn: int = 1,
        maxconn: int = 5,
    ) -> Dict[str, Any]:
        """MySQL 연결 풀 설정 저장 (실제 풀은 간단하게 구현)"""
        self._pool_config = self._make_conn_params(
            host=host, port=port, dbname=dbname, 
            user=user, password=password, sslmode=sslmode
        )
        self._min_connections = minconn
        self._max_connections = maxconn
        return self._pool_config
    
    def get_connection(self) -> Any:
        """연결 풀에서 연결 가져오기"""
        if self._pool_config is None:
            raise RuntimeError("연결 풀이 존재하지 않습니다. 먼저 create_pool을 호출하세요.")
        
        # 사용 가능한 연결이 있는지 확인
        for conn_id, conn in list(self._connections.items()):
            if conn and conn.open:
                del self._connections[conn_id]
                return conn
        
        # 새 연결 생성 (최대 연결 수 확인)
        if len(self._connections) < self._max_connections:
            conn = pymysql.connect(**self._pool_config)
            return conn
        
        raise RuntimeError("최대 연결 수에 도달했습니다.")
    
    def put_connection(self, conn: Any) -> None:
        """연결을 연결 풀에 반환"""
        if conn and conn.open and len(self._connections) < self._max_connections:
            conn_id = id(conn)
            self._connections[conn_id] = conn
        else:
            # 연결 종료
            try:
                if conn:
                    conn.close()
            except Exception:
                pass
    
    def close_pool(self) -> None:
        """연결 풀 종료"""
        for conn in self._connections.values():
            try:
                if conn and conn.open:
                    conn.close()
            except Exception:
                pass
        self._connections.clear()
        self._pool_config = None
    
    def test_connection(
        self,
        *,
        host: str,
        port: int,
        dbname: str,
        user: str,
        password: Optional[str],
        sslmode: Optional[str],
        timeout_seconds: int = 5,
    ) -> Tuple[bool, float, Optional[str]]:
        """MySQL 연결 테스트"""
        start = time.perf_counter()
        try:
            params = self._make_conn_params(
                host=host, port=port, dbname=dbname, 
                user=user, password=password, sslmode=sslmode
            )
            params["connect_timeout"] = timeout_seconds
            conn = pymysql.connect(**params)
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
            finally:
                conn.close()
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            return True, elapsed_ms, None
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            return False, elapsed_ms, str(e)


class SQLiteAdapter(DatabaseAdapter):
    """SQLite 어댑터 (sqlite3 기반)
    
    SQLite는 파일 기반이므로 연결 풀이 불필요합니다.
    각 요청마다 새로운 연결을 생성하고 즉시 종료합니다.
    """
    
    def __init__(self, database_id: str) -> None:
        super().__init__(database_id)
        self._db_path: Optional[str] = None
    
    def create_pool(
        self,
        *,
        host: str,
        port: int,
        dbname: str,
        user: str,
        password: Optional[str],
        sslmode: Optional[str],
        minconn: int = 1,
        maxconn: int = 5,
    ) -> str:
        """SQLite 데이터베이스 경로 설정
        
        SQLite는 연결 풀이 불필요하므로 파일 경로만 저장합니다.
        host가 'localhost'이거나 비어있으면 dbname을 파일 경로로 사용합니다.
        """
        # SQLite는 파일 기반이므로 host/port는 무시하고 dbname을 파일 경로로 사용
        if not dbname:
            raise ValueError("SQLite는 dbname(파일 경로)이 필요합니다.")
        
        # 절대 경로가 아니면 상대 경로로 처리
        if not dbname.startswith(('/')) and not (len(dbname) > 1 and dbname[1] == ':'):
            # Windows/Unix 절대 경로가 아닌 경우
            self._db_path = dbname
        else:
            self._db_path = dbname
        
        return self._db_path
    
    def get_connection(self) -> sqlite3.Connection:
        """SQLite 연결 생성"""
        if self._db_path is None:
            raise RuntimeError("데이터베이스 경로가 설정되지 않았습니다. 먼저 create_pool을 호출하세요.")
        
        conn = sqlite3.connect(self._db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row  # 딕셔너리 형태로 결과 반환
        return conn
    
    def put_connection(self, conn: sqlite3.Connection) -> None:
        """SQLite 연결 종료 (풀에 반환하지 않고 즉시 종료)"""
        try:
            if conn:
                conn.close()
        except Exception:
            pass
    
    def close_pool(self) -> None:
        """SQLite는 풀이 없으므로 경로만 초기화"""
        self._db_path = None
    
    def test_connection(
        self,
        *,
        host: str,
        port: int,
        dbname: str,
        user: str,
        password: Optional[str],
        sslmode: Optional[str],
        timeout_seconds: int = 5,
    ) -> Tuple[bool, float, Optional[str]]:
        """SQLite 연결 테스트"""
        start = time.perf_counter()
        try:
            if not dbname:
                raise ValueError("SQLite는 dbname(파일 경로)이 필요합니다.")
            
            conn = sqlite3.connect(dbname, timeout=float(timeout_seconds))
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
            finally:
                conn.close()
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            return True, elapsed_ms, None
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            return False, elapsed_ms, str(e)


def create_adapter(db_type: str, database_id: str) -> DatabaseAdapter:
    """DB 타입에 따른 어댑터 팩토리 함수"""
    db_type = db_type.lower().strip()
    
    if db_type == "postgresql":
        return PostgresAdapter(database_id)
    elif db_type == "mysql":
        return MySQLAdapter(database_id)
    elif db_type == "sqlite":
        return SQLiteAdapter(database_id)
    else:
        raise ValueError(f"지원하지 않는 데이터베이스 타입입니다: {db_type}")
