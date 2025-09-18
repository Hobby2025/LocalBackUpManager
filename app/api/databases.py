"""
데이터베이스 관리 API 라우터
데이터베이스 등록, 수정, 삭제, 조회 기능
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from app.database import get_db, Database, get_all_databases, get_database_by_id, create_database_record
from app.config import get_config_manager
from app.core.database_manager import db_manager
from app.core.auth import require_roles

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/", summary="모든 데이터베이스 조회")
async def get_databases(
    skip: int = 0,
    limit: int = 100,
    q: Optional[str] = Query(None, description="이름/표시명/호스트 검색"),
    db_type: Optional[str] = Query(None, description="데이터베이스 타입 필터 (postgresql, mysql, sqlite)"),
    environment: Optional[str] = Query(None, description="환경 필터"),
    priority: Optional[str] = Query(None, description="우선순위 필터"),
    status_filter: Optional[str] = Query(None, description="연결 상태 필터"),
    include_inactive: bool = Query(False, description="비활성 포함 여부"),
    sort: Optional[str] = Query(None, description="정렬 필드(name, db_type, environment, priority, host, port, connection_status)"),
    order: Optional[str] = Query("asc", description="정렬 방향 asc/desc"),
    page: Optional[int] = Query(None, ge=1, description="페이지 번호(선택)"),
    page_size: Optional[int] = Query(None, ge=1, le=500, description="페이지 크기(선택)"),
    db: Session = Depends(get_db)
):
    """등록된 데이터베이스 목록을 조회합니다. 검색/필터/정렬/페이징을 지원합니다."""
    try:
        query = db.query(Database)

        # 활성/비활성 필터
        if not include_inactive:
            query = query.filter(Database.is_active == True)

        # 텍스트 검색
        if q:
            like = f"%{q}%"
            query = query.filter(
                (Database.name.ilike(like)) |
                (Database.display_name.ilike(like)) |
                (Database.host.ilike(like))
            )

        # DB 타입/환경/우선순위/상태 필터
        if db_type:
            query = query.filter(Database.db_type == db_type)
        if environment:
            query = query.filter(Database.environment == environment)
        if priority:
            query = query.filter(Database.priority == priority)
        if status_filter:
            query = query.filter(Database.connection_status == status_filter)

        # 정렬
        sort_map = {
            "name": Database.name,
            "db_type": Database.db_type,
            "environment": Database.environment,
            "priority": Database.priority,
            "host": Database.host,
            "port": Database.port,
            "connection_status": Database.connection_status,
            "display_name": Database.display_name,
        }
        if sort in sort_map:
            sort_col = sort_map[sort]
            query = query.order_by(sort_col.desc() if (order or "asc").lower() == "desc" else sort_col.asc())
        else:
            query = query.order_by(Database.display_name.asc())

        total = query.count()

        # 페이징 우선, 없으면 skip/limit
        if page and page_size:
            offset = (page - 1) * page_size
            items = query.offset(offset).limit(page_size).all()
        else:
            items = query.offset(skip).limit(limit).all()

        return {
            "total": total,
            "databases": items,
            "page": page,
            "page_size": page_size,
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
    request: Request,
    db: Session = Depends(get_db)
):
    """새로운 데이터베이스를 시스템에 등록합니다. (admin 권한 필요)"""
    # 관리자 권한 검사
    if not require_roles(request, ("admin",)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다."
        )
    try:
        # 필수 필드 검증
        required_fields = ["name", "display_name", "host", "database_name", "username", "password", "environment", "priority"]
        for field in required_fields:
            if field not in database_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"필수 필드가 누락되었습니다: {field}"
                )
        
        # db_type 검증
        valid_db_types = ["postgresql", "mysql", "sqlite"]
        db_type = database_data.get("db_type", "postgresql")
        if db_type not in valid_db_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"지원하지 않는 데이터베이스 타입입니다. 지원 타입: {', '.join(valid_db_types)}"
            )
        
        # 환경 검증
        valid_environments = ["production", "staging", "development"]
        if database_data["environment"] not in valid_environments:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"올바르지 않은 환경입니다. 지원 환경: {', '.join(valid_environments)}"
            )
        
        # 우선순위 검증
        valid_priorities = ["high", "medium", "low"]
        if database_data["priority"] not in valid_priorities:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"올바르지 않은 우선순위입니다. 지원 우선순위: {', '.join(valid_priorities)}"
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
            db_type=db_type,
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
        updatable_fields = ["display_name", "host", "port", "database_name", "username", "ssl_mode", "db_type", "environment", "priority", "is_active"]
        
        # 필드별 검증
        for field in updatable_fields:
            if field in database_data:
                value = database_data[field]
                
                # db_type 검증
                if field == "db_type":
                    valid_db_types = ["postgresql", "mysql", "sqlite"]
                    if value not in valid_db_types:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"지원하지 않는 데이터베이스 타입입니다. 지원 타입: {', '.join(valid_db_types)}"
                        )
                
                # 환경 검증
                elif field == "environment":
                    valid_environments = ["production", "staging", "development"]
                    if value not in valid_environments:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"올바르지 않은 환경입니다. 지원 환경: {', '.join(valid_environments)}"
                        )
                
                # 우선순위 검증
                elif field == "priority":
                    valid_priorities = ["high", "medium", "low"]
                    if value not in valid_priorities:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"올바르지 않은 우선순위입니다. 지원 우선순위: {', '.join(valid_priorities)}"
                        )
                
                setattr(database, field, value)
        
        # 비밀번호 입력 정책: 공란 또는 미전달이면 유지, 값이 있으면 변경
        if "password" in database_data:
            pwd = database_data.get("password")
            if isinstance(pwd, str) and pwd.strip() != "":
                database.password_encrypted = pwd  # TODO: 암호화 적용 필요

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
    request: Request,
    db: Session = Depends(get_db)
):
    """데이터베이스를 시스템에서 제거합니다. (admin 권한 필요)"""
    # 관리자 권한 검사
    if not require_roles(request, ("admin",)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다."
        )
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

@router.get("/config", summary="databases.yaml 설정 조회 (환경변수 확장 적용)")
async def get_databases_config():
    """databases.yaml을 로드하고 환경변수 확장을 적용한 결과를 반환합니다."""
    try:
        cm = get_config_manager()
        data = cm.load_databases_config_expanded()
        return {"databases_config": data}
    except Exception as e:
        logger.error(f"설정 조회 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="설정 조회 중 오류가 발생했습니다."
        )

@router.post("/config/validate", summary="databases.yaml 설정 검증")
async def validate_databases_config():
    """databases.yaml 형식 및 필수 항목 검증 결과를 반환합니다."""
    try:
        cm = get_config_manager()
        result = cm.validate_databases_config()
        return result
    except Exception as e:
        logger.error(f"설정 검증 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="설정 검증 중 오류가 발생했습니다."
        )

@router.post("/config/reload", summary="databases.yaml 리로드")
async def reload_databases_config():
    """databases.yaml을 강제로 리로드하고, 변경 여부와 검증 결과를 반환합니다."""
    try:
        cm = get_config_manager()
        changed = cm.needs_reload("databases.yaml")
        data = cm.reload_databases_config()
        expanded = cm.expand_env_vars(data)
        validation = cm.validate_databases_config(expanded)
        return {
            "reloaded": True,
            "changed": changed,
            "databases_config": expanded,
            "validation": validation
        }
    except Exception as e:
        logger.error(f"설정 리로드 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="설정 리로드 중 오류가 발생했습니다."
        )
