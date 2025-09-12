"""
모니터링 API 라우터
시스템 상태, 성능 메트릭, 알림 관리 기능
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import logging
from datetime import datetime, timedelta

from app.database import get_db, Database, Backup, Schedule, SystemLog, Notification

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/status", summary="시스템 전체 상태 조회")
async def get_system_status(db: Session = Depends(get_db)):
    """시스템 전체 상태를 조회합니다."""
    try:
        # 데이터베이스 통계
        total_databases = db.query(Database).filter(Database.is_active == True).count()
        
        # 백업 통계 (최근 24시간)
        yesterday = datetime.now() - timedelta(days=1)
        recent_backups = db.query(Backup).filter(Backup.created_at >= yesterday).count()
        successful_backups = db.query(Backup).filter(
            Backup.created_at >= yesterday,
            Backup.status == "completed"
        ).count()
        failed_backups = db.query(Backup).filter(
            Backup.created_at >= yesterday,
            Backup.status == "failed"
        ).count()
        
        # 스케줄 통계
        active_schedules = db.query(Schedule).filter(Schedule.is_active == True).count()
        
        # 성공률 계산
        success_rate = (successful_backups / recent_backups * 100) if recent_backups > 0 else 0
        
        return {
            "system_status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "databases": {
                "total": total_databases,
                "active": total_databases
            },
            "backups": {
                "recent_24h": recent_backups,
                "successful": successful_backups,
                "failed": failed_backups,
                "success_rate": round(success_rate, 2)
            },
            "schedules": {
                "active": active_schedules
            }
        }
        
    except Exception as e:
        logger.error(f"시스템 상태 조회 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="시스템 상태 조회 중 오류가 발생했습니다."
        )

@router.get("/db-status", summary="데이터베이스 연결 상태 조회")
async def get_database_status(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """등록된 데이터베이스들의 연결 상태와 최근 테스트 시간을 조회합니다."""
    try:
        query = db.query(Database).filter(Database.is_active == True)
        total = query.count()
        items = query.order_by(Database.updated_at.desc()).offset(skip).limit(limit).all()
        results = []
        for it in items:
            results.append({
                "id": it.id,
                "name": it.name,
                "display_name": it.display_name,
                "environment": it.environment,
                "priority": it.priority,
                "connection_status": it.connection_status,
                "last_connection_test": it.last_connection_test.isoformat() if it.last_connection_test else None,
            })
        return {
            "total": total,
            "databases": results
        }
    except Exception as e:
        logger.error(f"데이터베이스 상태 조회 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="데이터베이스 상태 조회 중 오류가 발생했습니다."
        )

@router.get("/dashboard", summary="대시보드 데이터 조회")
async def get_dashboard_data(db: Session = Depends(get_db)):
    """대시보드에 필요한 종합 데이터를 조회합니다."""
    try:
        # 최근 7일간의 백업 통계
        week_ago = datetime.now() - timedelta(days=7)
        
        # 일별 백업 통계
        daily_stats = []
        for i in range(7):
            day_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=i)
            day_end = day_start + timedelta(days=1)
            
            day_backups = db.query(Backup).filter(
                Backup.created_at >= day_start,
                Backup.created_at < day_end
            ).count()
            
            day_successful = db.query(Backup).filter(
                Backup.created_at >= day_start,
                Backup.created_at < day_end,
                Backup.status == "completed"
            ).count()
            
            daily_stats.append({
                "date": day_start.strftime("%Y-%m-%d"),
                "total_backups": day_backups,
                "successful_backups": day_successful
            })
        
        # 최근 백업 목록
        recent_backups = db.query(Backup).order_by(
            Backup.created_at.desc()
        ).limit(10).all()
        
        # 활성 데이터베이스 목록
        active_databases = db.query(Database).filter(
            Database.is_active == True
        ).all()
        
        return {
            "daily_statistics": daily_stats,
            "recent_backups": recent_backups,
            "active_databases": active_databases,
            "summary": {
                "total_databases": len(active_databases),
                "total_backups_week": sum(stat["total_backups"] for stat in daily_stats),
                "successful_backups_week": sum(stat["successful_backups"] for stat in daily_stats)
            }
        }
        
    except Exception as e:
        logger.error(f"대시보드 데이터 조회 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="대시보드 데이터 조회 중 오류가 발생했습니다."
        )

@router.get("/logs", summary="시스템 로그 조회")
async def get_system_logs(
    skip: int = 0,
    limit: int = 100,
    level: Optional[str] = None,
    component: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """시스템 로그를 조회합니다."""
    try:
        query = db.query(SystemLog)
        
        if level:
            query = query.filter(SystemLog.level == level)
        
        if component:
            query = query.filter(SystemLog.component == component)
        
        logs = query.order_by(SystemLog.created_at.desc()).offset(skip).limit(limit).all()
        total = query.count()
        
        return {
            "total": total,
            "logs": logs
        }
        
    except Exception as e:
        logger.error(f"시스템 로그 조회 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="시스템 로그 조회 중 오류가 발생했습니다."
        )

@router.get("/notifications", summary="알림 이력 조회")
async def get_notifications(
    skip: int = 0,
    limit: int = 50,
    level: Optional[str] = None,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """알림 이력을 조회합니다."""
    try:
        query = db.query(Notification)
        
        if level:
            query = query.filter(Notification.level == level)
        
        if status_filter:
            query = query.filter(Notification.status == status_filter)
        
        notifications = query.order_by(Notification.created_at.desc()).offset(skip).limit(limit).all()
        total = query.count()
        
        return {
            "total": total,
            "notifications": notifications
        }
        
    except Exception as e:
        logger.error(f"알림 이력 조회 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="알림 이력 조회 중 오류가 발생했습니다."
        )

@router.get("/metrics", summary="성능 메트릭 조회")
async def get_performance_metrics(db: Session = Depends(get_db)):
    """시스템 성능 메트릭을 조회합니다."""
    try:
        # 백업 성능 통계
        avg_duration = db.query(func.avg(Backup.duration_seconds)).filter(
            Backup.status == "completed",
            Backup.duration_seconds.isnot(None)
        ).scalar() or 0
        
        avg_size = db.query(func.avg(Backup.file_size)).filter(
            Backup.status == "completed",
            Backup.file_size.isnot(None)
        ).scalar() or 0
        
        avg_compression_ratio = db.query(func.avg(Backup.compression_ratio)).filter(
            Backup.status == "completed",
            Backup.compression_ratio.isnot(None)
        ).scalar() or 0
        
        return {
            "backup_performance": {
                "average_duration_seconds": round(avg_duration, 2),
                "average_file_size_bytes": int(avg_size),
                "average_compression_ratio": round(avg_compression_ratio, 2)
            },
            "system_resources": {
                "disk_usage": "TODO: 구현 필요",
                "memory_usage": "TODO: 구현 필요",
                "cpu_usage": "TODO: 구현 필요"
            }
        }
        
    except Exception as e:
        logger.error(f"성능 메트릭 조회 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="성능 메트릭 조회 중 오류가 발생했습니다."
        )
