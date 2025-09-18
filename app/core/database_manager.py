"""
다중 데이터베이스 연결/풀/상태 관리 매니저 (어댑터 패턴 기반)
- PostgreSQL, MySQL, SQLite 지원
- 어댑터 패턴으로 DB별 최적화된 연결 관리
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
from typing import Any, Dict, Optional, Tuple

from app.core.database_adapters import DatabaseAdapter, create_adapter

# 내부 모델에 직접 의존하지 않도록 최소한의 인터페이스만 사용
# app.api 계층에서 SQLAlchemy 모델(Database)을 전달받아 필요한 필드만 활용


class DatabaseManager:
    """다중 데이터베이스 연결/풀/상태 관리 클래스 (어댑터 패턴 기반)"""

    def __init__(self) -> None:
        # 데이터베이스별로 어댑터를 관리 (key: database.id)
        self._adapters: Dict[str, DatabaseAdapter] = {}

    # -----------------------------
    # 내부 유틸리티
    # -----------------------------
    def _get_adapter(self, database_id: str, db_type: str) -> DatabaseAdapter:
        """데이터베이스 어댑터 가져오기 (없으면 생성)"""
        adapter = self._adapters.get(database_id)
        if adapter is None:
            adapter = create_adapter(db_type, database_id)
            self._adapters[database_id] = adapter
        return adapter

    # -----------------------------
    # 공개 API: 연결 풀 관리
    # -----------------------------
    def get_or_create_pool(
        self,
        *,
        database_id: str,
        db_type: str,
        host: str,
        port: int,
        dbname: str,
        user: str,
        password: Optional[str],
        sslmode: Optional[str],
        minconn: int = 1,
        maxconn: int = 5,
    ) -> Any:
        """해당 데이터베이스에 대한 연결 풀을 반환 (없으면 생성)
        - 어댑터 패턴으로 DB 타입별 최적화된 풀 생성
        """
        adapter = self._get_adapter(database_id, db_type)
        return adapter.create_pool(
            host=host, port=port, dbname=dbname, 
            user=user, password=password, sslmode=sslmode,
            minconn=minconn, maxconn=maxconn
        )

    def get_connection(self, database_id: str, db_type: str) -> Any:
        """연결 풀에서 연결을 하나 가져옵니다."""
        adapter = self._adapters.get(database_id)
        if adapter is None:
            raise RuntimeError("연결 풀이 존재하지 않습니다. 먼저 get_or_create_pool을 호출하세요.")
        return adapter.get_connection()

    def put_connection(self, database_id: str, conn: Any) -> None:
        """연결을 연결 풀에 반환합니다."""
        adapter = self._adapters.get(database_id)
        if adapter is None:
            # 어댑터가 이미 제거된 경우 안전하게 종료만 시도
            try:
                if hasattr(conn, 'close'):
                    conn.close()
            finally:
                return
        adapter.put_connection(conn)

    def close_pool(self, database_id: str) -> None:
        """특정 데이터베이스의 연결 풀을 종료합니다."""
        adapter = self._adapters.pop(database_id, None)
        if adapter is not None:
            adapter.close_pool()

    def close_all(self) -> None:
        """모든 연결 풀을 종료합니다."""
        for database_id, adapter in list(self._adapters.items()):
            try:
                adapter.close_pool()
            finally:
                self._adapters.pop(database_id, None)

    # -----------------------------
    # 공개 API: 연결 테스트/상태
    # -----------------------------
    def test_connection(
        self,
        *,
        db_type: str,
        host: str,
        port: int,
        dbname: str,
        user: str,
        password: Optional[str],
        sslmode: Optional[str],
        timeout_seconds: int = 5,
    ) -> Tuple[bool, float, Optional[str]]:
        """
        DB 연결 테스트 수행 (어댑터 기반)
        반환: (성공여부, 응답시간(ms), 오류메시지)
        """
        # 임시 어댑터를 생성하여 테스트 수행 (풀에 저장하지 않음)
        temp_adapter = create_adapter(db_type, "temp_test")
        return temp_adapter.test_connection(
            host=host, port=port, dbname=dbname,
            user=user, password=password, sslmode=sslmode,
            timeout_seconds=timeout_seconds
        )

    def get_status_summary(self) -> Dict[str, int]:
        """
        간단한 상태 요약 반환
        - 관리 중인 어댑터 개수 등 메타 정보 제공
        """
        return {
            "managed_adapters": len(self._adapters),
        }


# 모듈 전역 싱글턴 인스턴스 (필요 시 주입 가능)
db_manager = DatabaseManager()
