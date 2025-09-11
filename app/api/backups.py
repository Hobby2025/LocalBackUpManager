"""
백업 관리 API 라우터
백업 실행, 조회, 복원, 통계 기능
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from app.database import get_db, Backup, get_backups_by_database, create_backup_record
from app.core.backup_engine import BackupEngine  # 백업 엔진

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/", summary="모든 백업 이력 조회")
async def get_backups(
    skip: int = 0,
    limit: int = 50,
    database_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """백업 이력을 조회합니다."""
    try:
        query = db.query(Backup)
        
        if database_id:
            query = query.filter(Backup.database_id == database_id)
        
        if status_filter:
            query = query.filter(Backup.status == status_filter)
        
        backups = query.order_by(Backup.created_at.desc()).offset(skip).limit(limit).all()
        total = query.count()
        
        return {
            "total": total,
            "backups": backups
        }
    except Exception as e:
        logger.error(f"백업 이력 조회 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="백업 이력 조회 중 오류가 발생했습니다."
        )

@router.get("/{backup_id}", summary="특정 백업 상세 조회")
async def get_backup(
    backup_id: str,
    db: Session = Depends(get_db)
):
    """특정 백업의 상세 정보를 조회합니다."""
    try:
        backup = db.query(Backup).filter(Backup.id == backup_id).first()
        if not backup:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="백업을 찾을 수 없습니다."
            )
        return backup
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"백업 조회 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="백업 조회 중 오류가 발생했습니다."
        )

@router.post("/database/{database_id}", summary="백업 실행")
async def create_backup(
    database_id: str,
    backup_data: dict,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None,
):
    """새로운 백업을 실행합니다."""
    try:
        backup_type = backup_data.get("backup_type", "full")
        
        # 백업 레코드 생성
        new_backup = create_backup_record(
            db,
            database_id=database_id,
            backup_type=backup_type,
            status="pending"
        )
        
        # 실제 백업 작업을 백그라운드에서 실행
        # - FastAPI BackgroundTasks를 사용하여 요청과 분리
        if background_tasks is not None:
            background_tasks.add_task(BackupEngine().run_backup, database_id, new_backup.id)
        logger.info(f"백업 작업 시작(백그라운드): {new_backup.id}")
        
        return {
            "message": "백업이 시작되었습니다.",
            "backup_id": new_backup.id,
            "status": "pending"
        }
        
    except Exception as e:
        logger.error(f"백업 실행 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="백업 실행 중 오류가 발생했습니다."
        )

@router.post("/{backup_id}/cancel", summary="백업 취소")
async def cancel_backup(
    backup_id: str,
    db: Session = Depends(get_db)
):
    """실행 중인 백업을 취소합니다."""
    try:
        backup = db.query(Backup).filter(Backup.id == backup_id).first()
        if not backup:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="백업을 찾을 수 없습니다."
            )
        
        if backup.status not in ["pending", "running"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="취소할 수 없는 백업 상태입니다."
            )
        
        backup.status = "cancelled"
        db.commit()
        
        logger.info(f"백업 취소됨: {backup_id}")
        return {"message": "백업이 취소되었습니다."}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"백업 취소 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="백업 취소 중 오류가 발생했습니다."
        )

@router.get("/database/{database_id}/statistics", summary="데이터베이스 백업 통계")
async def get_backup_statistics(
    database_id: str,
    db: Session = Depends(get_db)
):
    """특정 데이터베이스의 백업 통계를 조회합니다."""
    try:
        # 기본 통계 쿼리
        total_backups = db.query(Backup).filter(Backup.database_id == database_id).count()
        successful_backups = db.query(Backup).filter(
            Backup.database_id == database_id,
            Backup.status == "completed"
        ).count()
        failed_backups = db.query(Backup).filter(
            Backup.database_id == database_id,
            Backup.status == "failed"
        ).count()
        
        success_rate = (successful_backups / total_backups * 100) if total_backups > 0 else 0
        
        return {
            "database_id": database_id,
            "total_backups": total_backups,
            "successful_backups": successful_backups,
            "failed_backups": failed_backups,
            "success_rate": round(success_rate, 2),
            "statistics": {
                "avg_backup_size": 0,  # TODO: 실제 계산
                "avg_duration": 0,     # TODO: 실제 계산
                "last_backup": None    # TODO: 실제 조회
            }
        }
        
    except Exception as e:
        logger.error(f"백업 통계 조회 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="백업 통계 조회 중 오류가 발생했습니다."
        )
