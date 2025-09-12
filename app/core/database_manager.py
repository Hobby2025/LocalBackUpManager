"""
다중 데이터베이스 연결/풀/상태 관리 매니저
- psycopg2 SimpleConnectionPool 기반 연결 풀 관리
- 연결 테스트 기능 제공
- 상태 요약 및 리소스 정리 지원

주의:
- 변수명은 기존 코드와 충돌하지 않도록 새로운 범위에서만 정의
- 외부 의존성 추가 금지 (requirements.txt 내 패키지만 사용)
- Windows/Unix 환경 모두 동작
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Dict, Optional, Tuple

import psycopg2
from psycopg2.pool import SimpleConnectionPool

# 내부 모델에 직접 의존하지 않도록 최소한의 인터페이스만 사용
# app.api 계층에서 SQLAlchemy 모델(Database)을 전달받아 필요한 필드만 활용


class DatabaseManager:
    """다중 데이터베이스 연결/풀/상태 관리 클래스"""

    def __init__(self) -> None:
        # 데이터베이스별로 연결 풀을 관리 (key: database.id)
        self._pools: Dict[str, SimpleConnectionPool] = {}

    # -----------------------------
    # 내부 유틸리티
    # -----------------------------
    def _make_conn_params(self, *, host: str, port: int, dbname: str, user: str, password: Optional[str], sslmode: Optional[str]) -> Dict[str, object]:
        """psycopg2 연결 파라미터 구성
        - connect_timeout 기본 5초
        - sslmode는 Database.ssl_mode 값을 그대로 전달 (없으면 require 기본 가정 가능)
        """
        params: Dict[str, object] = {
            "host": host,
            "port": int(port) if port is not None else 5432,
            "dbname": dbname,
            "user": user,
            "connect_timeout": 5,
        }
        if password:
            params["password"] = password
        if sslmode:
            params["sslmode"] = sslmode
        return params

    def _pool_key(self, database_id: str) -> str:
        return str(database_id)

    # -----------------------------
    # 공개 API: 연결 풀 관리
    # -----------------------------
    def get_or_create_pool(
        self,
        *,
        database_id: str,
        host: str,
        port: int,
        dbname: str,
        user: str,
        password: Optional[str],
        sslmode: Optional[str],
        minconn: int = 1,
        maxconn: int = 5,
    ) -> SimpleConnectionPool:
        """해당 데이터베이스에 대한 연결 풀을 반환 (없으면 생성)
        - 연결 풀은 SimpleConnectionPool(minconn, maxconn, **params) 사용
        """
        key = self._pool_key(database_id)
        pool = self._pools.get(key)
        if pool is None:
            params = self._make_conn_params(host=host, port=port, dbname=dbname, user=user, password=password, sslmode=sslmode)
            pool = SimpleConnectionPool(minconn, maxconn, **params)
            self._pools[key] = pool
        return pool

    def get_connection(self, database_id: str) -> psycopg2.extensions.connection:
        """연결 풀에서 연결을 하나 가져옵니다."""
        key = self._pool_key(database_id)
        pool = self._pools.get(key)
        if pool is None:
            raise RuntimeError("연결 풀이 존재하지 않습니다. 먼저 get_or_create_pool을 호출하세요.")
        return pool.getconn()

    def put_connection(self, database_id: str, conn: psycopg2.extensions.connection) -> None:
        """연결을 연결 풀에 반환합니다."""
        key = self._pool_key(database_id)
        pool = self._pools.get(key)
        if pool is None:
            # 풀이 이미 제거된 경우 안전하게 종료만 시도
            try:
                conn.close()
            finally:
                return
        pool.putconn(conn)

    def close_pool(self, database_id: str) -> None:
        """특정 데이터베이스의 연결 풀을 종료합니다."""
        key = self._pool_key(database_id)
        pool = self._pools.pop(key, None)
        if pool is not None:
            pool.closeall()

    def close_all(self) -> None:
        """모든 연결 풀을 종료합니다."""
        for key, pool in list(self._pools.items()):
            try:
                pool.closeall()
            finally:
                self._pools.pop(key, None)

    # -----------------------------
    # 공개 API: 연결 테스트/상태
    # -----------------------------
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
        """DB 연결 테스트 수행
        반환: (성공여부, 응답시간(ms), 오류메시지)
        """
        start = time.perf_counter()
        try:
            params = self._make_conn_params(host=host, port=port, dbname=dbname, user=user, password=password, sslmode=sslmode)
            # 개별 테스트는 풀을 거치지 않고 직접 연결하여 지연/에러 측정
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

    def get_status_summary(self) -> Dict[str, int]:
        """간단한 상태 요약 반환
        - 관리 중인 풀 개수 등 메타 정보 제공
        """
        return {
            "managed_pools": len(self._pools),
        }


# 모듈 전역 싱글턴 인스턴스 (필요 시 주입 가능)
db_manager = DatabaseManager()
