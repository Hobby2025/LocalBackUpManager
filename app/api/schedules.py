"""
스케줄 관리 API 라우터
백업 스케줄 생성, 수정, 삭제, 조회 기능
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from app.database import get_db, Schedule

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/", summary="모든 스케줄 조회")
async def get_schedules(
    skip: int = 0,
    limit: int = 100,
    database_id: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """등록된 모든 백업 스케줄을 조회합니다."""
    try:
        query = db.query(Schedule)
        
        if database_id:
            query = query.filter(Schedule.database_id == database_id)
        
        if is_active is not None:
            query = query.filter(Schedule.is_active == is_active)
        
        schedules = query.order_by(Schedule.created_at.desc()).offset(skip).limit(limit).all()
        total = query.count()
        
        return {
            "total": total,
            "schedules": schedules
        }
    except Exception as e:
        logger.error(f"스케줄 목록 조회 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="스케줄 목록 조회 중 오류가 발생했습니다."
        )

@router.get("/{schedule_id}", summary="특정 스케줄 조회")
async def get_schedule(
    schedule_id: str,
    db: Session = Depends(get_db)
):
    """특정 스케줄의 상세 정보를 조회합니다."""
    try:
        schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
        if not schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="스케줄을 찾을 수 없습니다."
            )
        return schedule
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"스케줄 조회 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="스케줄 조회 중 오류가 발생했습니다."
        )

@router.post("/database/{database_id}", summary="새 스케줄 생성")
async def create_schedule(
    database_id: str,
    schedule_data: dict,
    db: Session = Depends(get_db)
):
    """새로운 백업 스케줄을 생성합니다."""
    try:
        # 필수 필드 검증
        required_fields = ["schedule_type", "cron_expression"]
        for field in required_fields:
            if field not in schedule_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"필수 필드가 누락되었습니다: {field}"
                )
        
        # 스케줄 생성
        new_schedule = Schedule(
            database_id=database_id,
            schedule_type=schedule_data["schedule_type"],
            cron_expression=schedule_data["cron_expression"],
            timezone=schedule_data.get("timezone", "UTC"),
            is_active=schedule_data.get("is_active", True),
            max_retries=schedule_data.get("max_retries", 3)
        )
        
        db.add(new_schedule)
        db.commit()
        db.refresh(new_schedule)
        
        logger.info(f"새 스케줄 생성됨: {new_schedule.id}")
        return {
            "message": "스케줄이 성공적으로 생성되었습니다.",
            "schedule_id": new_schedule.id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"스케줄 생성 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="스케줄 생성 중 오류가 발생했습니다."
        )

@router.put("/{schedule_id}", summary="스케줄 수정")
async def update_schedule(
    schedule_id: str,
    schedule_data: dict,
    db: Session = Depends(get_db)
):
    """기존 스케줄을 수정합니다."""
    try:
        schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
        if not schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="스케줄을 찾을 수 없습니다."
            )
        
        # 업데이트 가능한 필드들
        updatable_fields = ["cron_expression", "timezone", "is_active", "max_retries"]
        
        for field in updatable_fields:
            if field in schedule_data:
                setattr(schedule, field, schedule_data[field])
        
        db.commit()
        db.refresh(schedule)
        
        logger.info(f"스케줄 수정됨: {schedule_id}")
        return {
            "message": "스케줄이 성공적으로 수정되었습니다.",
            "schedule": schedule
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"스케줄 수정 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="스케줄 수정 중 오류가 발생했습니다."
        )

@router.delete("/{schedule_id}", summary="스케줄 삭제")
async def delete_schedule(
    schedule_id: str,
    db: Session = Depends(get_db)
):
    """스케줄을 삭제합니다."""
    try:
        schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
        if not schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="스케줄을 찾을 수 없습니다."
            )
        
        # 스케줄 비활성화 (소프트 삭제)
        schedule.is_active = False
        db.commit()
        
        logger.info(f"스케줄 삭제됨: {schedule_id}")
        return {"message": "스케줄이 성공적으로 삭제되었습니다."}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"스케줄 삭제 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="스케줄 삭제 중 오류가 발생했습니다."
        )

@router.post("/{schedule_id}/toggle", summary="스케줄 활성화/비활성화")
async def toggle_schedule(
    schedule_id: str,
    db: Session = Depends(get_db)
):
    """스케줄을 활성화하거나 비활성화합니다."""
    try:
        schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
        if not schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="스케줄을 찾을 수 없습니다."
            )
        
        schedule.is_active = not schedule.is_active
        db.commit()
        
        status_text = "활성화" if schedule.is_active else "비활성화"
        logger.info(f"스케줄 {status_text}됨: {schedule_id}")
        
        return {
            "message": f"스케줄이 {status_text}되었습니다.",
            "is_active": schedule.is_active
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"스케줄 토글 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="스케줄 상태 변경 중 오류가 발생했습니다."
        )
