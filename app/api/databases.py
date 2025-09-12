"""
데이터베이스 관리 API 라우터
데이터베이스 등록, 수정, 삭제, 조회 기능
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from app.database import get_db, Database, get_all_databases, get_database_by_id, create_database_record
from app.config import get_config_manager
from app.core.database_manager import db_manager

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/", summary="모든 데이터베이스 조회")
async def get_databases(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """등록된 모든 데이터베이스 목록을 조회합니다."""
    try:
        databases = get_all_databases(db)
        return {
            "total": len(databases),
            "databases": databases[skip:skip + limit]
        }
    except Exception as e:
        logger.error(f"데이터베이스 목록 조회 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="데이터베이스 목록 조회 중 오류가 발생했습니다."
        )

@router.get("/{database_id}", summary="특정 데이터베이스 조회")
async def get_database(
    database_id: str,
    db: Session = Depends(get_db)
):
    """특정 데이터베이스의 상세 정보를 조회합니다."""
    try:
        database = get_database_by_id(db, database_id)
        if not database:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="데이터베이스를 찾을 수 없습니다."
            )
        return database
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"데이터베이스 조회 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="데이터베이스 조회 중 오류가 발생했습니다."
        )

@router.post("/", summary="새 데이터베이스 등록")
async def create_database(
    database_data: dict,
    db: Session = Depends(get_db)
):
    """새로운 데이터베이스를 시스템에 등록합니다."""
    try:
        # 필수 필드 검증
        required_fields = ["name", "display_name", "host", "database_name", "username", "password", "environment", "priority"]
        for field in required_fields:
            if field not in database_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"필수 필드가 누락되었습니다: {field}"
                )
        
        # 데이터베이스 생성
        new_database = create_database_record(
            db,
            name=database_data["name"],
            display_name=database_data["display_name"],
            host=database_data["host"],
            port=database_data.get("port", 5432),
            database_name=database_data["database_name"],
            username=database_data["username"],
            password_encrypted=database_data["password"],  # TODO: 암호화 구현
            ssl_mode=database_data.get("ssl_mode", "require"),
            environment=database_data["environment"],
            priority=database_data["priority"]
        )
        
        logger.info(f"새 데이터베이스 등록됨: {new_database.name}")
        return {
            "message": "데이터베이스가 성공적으로 등록되었습니다.",
            "database_id": new_database.id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"데이터베이스 등록 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="데이터베이스 등록 중 오류가 발생했습니다."
        )

@router.put("/{database_id}", summary="데이터베이스 정보 수정")
async def update_database(
    database_id: str,
    database_data: dict,
    db: Session = Depends(get_db)
):
    """기존 데이터베이스의 정보를 수정합니다."""
    try:
        database = get_database_by_id(db, database_id)
        if not database:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="데이터베이스를 찾을 수 없습니다."
            )
        
        # 업데이트 가능한 필드들
        updatable_fields = ["display_name", "host", "port", "database_name", "username", "ssl_mode", "environment", "priority", "is_active"]
        
        for field in updatable_fields:
            if field in database_data:
                setattr(database, field, database_data[field])
        
        db.commit()
        db.refresh(database)
        
        logger.info(f"데이터베이스 정보 수정됨: {database.name}")
        return {
            "message": "데이터베이스 정보가 성공적으로 수정되었습니다.",
            "database": database
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"데이터베이스 수정 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="데이터베이스 수정 중 오류가 발생했습니다."
        )

@router.delete("/{database_id}", summary="데이터베이스 삭제")
async def delete_database(
    database_id: str,
    db: Session = Depends(get_db)
):
    """데이터베이스를 시스템에서 제거합니다."""
    try:
        database = get_database_by_id(db, database_id)
        if not database:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="데이터베이스를 찾을 수 없습니다."
            )
        
        # 소프트 삭제 (is_active = False)
        database.is_active = False
        db.commit()
        
        logger.info(f"데이터베이스 삭제됨: {database.name}")
        return {"message": "데이터베이스가 성공적으로 삭제되었습니다."}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"데이터베이스 삭제 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="데이터베이스 삭제 중 오류가 발생했습니다."
        )

@router.post("/{database_id}/test-connection", summary="데이터베이스 연결 테스트")
async def test_database_connection(
    database_id: str,
    db: Session = Depends(get_db)
):
    """데이터베이스 연결을 테스트합니다."""
    try:
        database = get_database_by_id(db, database_id)
        if not database:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="데이터베이스를 찾을 수 없습니다."
            )

        # 실제 연결 테스트 수행 (현재 password_encrypted는 평문 비밀번호 사용 가정)
        success, elapsed_ms, error_msg = db_manager.test_connection(
            host=database.host,
            port=database.port,
            dbname=database.database_name,
            user=database.username,
            password=database.password_encrypted,
            sslmode=database.ssl_mode,
            timeout_seconds=5,
        )

        # 상태 및 타임스탬프 갱신
        from datetime import datetime
        database.last_connection_test = datetime.utcnow()
        database.connection_status = "connected" if success else "error"
        db.commit()
        db.refresh(database)

        return {
            "database_id": database_id,
            "status": "success" if success else "failed",
            "message": "데이터베이스 연결이 성공했습니다." if success else (error_msg or "연결 오류가 발생했습니다."),
            "response_time_ms": round(elapsed_ms, 2)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"데이터베이스 연결 테스트 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="데이터베이스 연결 테스트 중 오류가 발생했습니다."
        )
