"""
모니터링 API 라우터
시스템 상태, 성능 메트릭, 알림 관리 기능
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from pathlib import Path
import os
import csv
import json
import uuid
import asyncio
import logging
from datetime import datetime, timedelta

from app.database import get_db, Database, Backup, Schedule, SystemLog, Notification, User
from app.core.auth import is_auth_enabled, get_current_user_from_request
from app.core.notification_service import NotificationService

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


@router.get("/realtime", summary="실시간 모니터링 요약")
async def get_realtime_summary(db: Session = Depends(get_db)):
    """최근 백업/알림 이력을 요약으로 제공 (폴링 기반 실시간용)
    - 최근 10개 백업, 최근 20개 알림
    - 최근 1시간 집계 요약
    """
    try:
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        # 최근 백업 10건
        recent_backups_rows = db.query(Backup).order_by(Backup.created_at.desc()).limit(10).all()
        recent_backups = [
            {
                "id": row.id,
                "database_id": row.database_id,
                "status": row.status,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in recent_backups_rows
        ]
        # 최근 알림 20건
        recent_notifs_rows = db.query(Notification).order_by(Notification.created_at.desc()).limit(20).all()
        recent_notifications = [
            {
                "id": n.id,
                "level": n.level,
                "status": n.status,
                "title": n.title,
                "notification_type": n.notification_type,
                "created_at": n.created_at.isoformat() if getattr(n, "created_at", None) else None,
            }
            for n in recent_notifs_rows
        ]
        # 최근 1시간 요약
        backups_1h = db.query(Backup).filter(Backup.created_at >= one_hour_ago).count()
        success_1h = db.query(Backup).filter(Backup.created_at >= one_hour_ago, Backup.status == "completed").count()
        failed_1h = db.query(Backup).filter(Backup.created_at >= one_hour_ago, Backup.status == "failed").count()
        success_rate_1h = (success_1h / backups_1h * 100) if backups_1h > 0 else 0
        return {
            "timestamp": now.isoformat(),
            "recent_backups": recent_backups,
            "recent_notifications": recent_notifications,
            "summary_1h": {
                "total": backups_1h,
                "successful": success_1h,
                "failed": failed_1h,
                "success_rate": round(success_rate_1h, 2),
            },
        }
    except Exception as e:
        logger.error(f"실시간 요약 조회 오류: {e}")
        raise HTTPException(status_code=500, detail="실시간 요약 조회 중 오류")


@router.post("/reports/generate", summary="모니터링 보고서 생성")
async def generate_report(
    hours: int = 24,
    status_filter: Optional[str] = None,
    notify: bool = False,
    retention_days: int = 7,
    db: Session = Depends(get_db)
):
    """최근 hours 시간 범위의 백업 이력을 CSV 보고서로 생성
    - 결과 파일은 data/reports 에 저장되고 /static/reports 로 서빙됨
    - 반환: 보고서 파일명/URL/건수
    """
    try:
        hours = max(1, min(hours, 24 * 7))  # 1시간~7일 제한
        now = datetime.now()
        since = now - timedelta(hours=hours)
        q = db.query(Backup).filter(Backup.created_at >= since)
        if status_filter:
            q = q.filter(Backup.status == status_filter)
        rows = q.order_by(Backup.created_at.asc()).all()
        # 저장 경로 준비
        reports_dir = Path("data/reports")
        reports_dir.mkdir(parents=True, exist_ok=True)
        # 파일명 중복 방지를 위해 짧은 UUID suffix를 추가
        suffix = uuid.uuid4().hex[:6]
        filename = f"report_{now.strftime('%Y%m%d_%H%M%S')}_{suffix}.csv"
        filepath = reports_dir / filename
        # CSV 작성
        with filepath.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            # 헤더
            writer.writerow([
                "backup_id",
                "database_id",
                "status",
                "duration_seconds",
                "file_size",
                "compressed_size",
                "compression_ratio",
                "created_at",
                "completed_at",
            ])
            for r in rows:
                writer.writerow([
                    r.id,
                    r.database_id,
                    r.status,
                    r.duration_seconds,
                    r.file_size,
                    r.compressed_size,
                    r.compression_ratio,
                    r.created_at.isoformat() if r.created_at else "",
                    r.completed_at.isoformat() if getattr(r, "completed_at", None) else "",
                ])
        # 보존기간(retention_days) 초과 파일 정리
        try:
            if retention_days and retention_days > 0:
                cutoff = now - timedelta(days=retention_days)
                for p in reports_dir.glob('report_*.csv'):
                    try:
                        if datetime.fromtimestamp(p.stat().st_mtime) < cutoff:
                            p.unlink(missing_ok=True)
                    except Exception:
                        pass
        except Exception as _clean_err:
            logger.warning(f"보고서 정리 경고: {_clean_err}")

        # 필요시 알림 채널로 결과 전송(브로드캐스트)
        if notify:
            try:
                svc = NotificationService()
                title = "[보고서 생성] 백업 리포트 생성 완료"
                msg = (
                    f"기간: 최근 {hours}시간, 상태필터: {status_filter or '전체'}\n"
                    f"건수: {len(rows)}\n"
                    f"다운로드: /static/reports/{filename}"
                )
                svc.broadcast(title=title, message=msg)
            except Exception as _nerr:
                logger.warning(f"보고서 알림 전송 경고: {_nerr}")

        return {
            "status": "ok",
            "filename": filename,
            "report_url": f"/static/reports/{filename}",
            "count": len(rows),
            "since": since.isoformat(),
            "generated_at": now.isoformat(),
        }
    except Exception as e:
        logger.error(f"보고서 생성 오류: {e}")
        raise HTTPException(status_code=500, detail="보고서 생성 중 오류")


@router.get("/realtime/stream", summary="실시간 모니터링 SSE 스트림")
async def realtime_stream(db: Session = Depends(get_db)):
    """Server-Sent Events로 주기적으로 실시간 요약을 전송
    - 클라이언트는 EventSource로 수신
    - 5초 간격으로 전송
    """
    async def event_generator():
        try:
            while True:
                now = datetime.now()
                one_hour_ago = now - timedelta(hours=1)
                backups_1h = db.query(Backup).filter(Backup.created_at >= one_hour_ago).count()
                success_1h = db.query(Backup).filter(Backup.created_at >= one_hour_ago, Backup.status == "completed").count()
                failed_1h = db.query(Backup).filter(Backup.created_at >= one_hour_ago, Backup.status == "failed").count()
                success_rate_1h = (success_1h / backups_1h * 100) if backups_1h > 0 else 0
                recent_notifs_rows = db.query(Notification).order_by(Notification.created_at.desc()).limit(20).all()
                recent_notifications = [
                    {
                        "id": n.id,
                        "level": n.level,
                        "status": n.status,
                        "title": n.title,
                        "notification_type": n.notification_type,
                        "created_at": n.created_at.isoformat() if getattr(n, "created_at", None) else None,
                    }
                    for n in recent_notifs_rows
                ]
                payload = {
                    "timestamp": now.isoformat(),
                    "summary_1h": {
                        "total": backups_1h,
                        "successful": success_1h,
                        "failed": failed_1h,
                        "success_rate": round(success_rate_1h, 2),
                    },
                    "recent_notifications": recent_notifications,
                }
                data = json.dumps(payload)
                yield f"data: {data}\n\n"
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            # 클라이언트 연결 종료
            return
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/reports/list", summary="생성된 보고서 목록")
async def list_reports(db: Session = Depends(get_db)):
    """data/reports 폴더의 보고서 파일 목록 제공
    - 반환: filename, url, size_bytes, modified_at
    """
    try:
        reports_dir = Path("data/reports")
        reports_dir.mkdir(parents=True, exist_ok=True)
        items = []
        for p in sorted(reports_dir.glob('report_*.csv'), key=lambda x: x.stat().st_mtime, reverse=True):
            st = p.stat()
            items.append({
                "filename": p.name,
                "url": f"/static/reports/{p.name}",
                "size_bytes": st.st_size,
                "modified_at": datetime.fromtimestamp(st.st_mtime).isoformat(),
            })
        return {"reports": items}
    except Exception as e:
        logger.error(f"보고서 목록 조회 오류: {e}")
        raise HTTPException(status_code=500, detail="보고서 목록 조회 중 오류")


@router.delete("/reports/{filename}", summary="보고서 삭제")
async def delete_report(filename: str, db: Session = Depends(get_db), request=None):
    """보고서 파일을 안전하게 삭제
    - filename은 report_*.csv 패턴만 허용
    """
    try:
        # 인증/권한 체크: 인증 활성화 시 admin 역할만 허용
        if is_auth_enabled():
            # Request 주입을 위해 FastAPI가 request 객체를 전달함
            from fastapi import Request
            if not isinstance(request, Request):
                raise HTTPException(status_code=401, detail="인증 필요")
            username = get_current_user_from_request(request)
            if not username:
                raise HTTPException(status_code=401, detail="인증 필요")
            user = db.query(User).filter(User.username == username, User.is_active == True).first()
            if not user or (user.role or '').lower() != 'admin':
                raise HTTPException(status_code=403, detail="권한 없음")

        # 파일명 패턴 검증 (디렉터리 탈출 방지)
        if not filename.startswith("report_") or not filename.endswith(".csv"):
            raise HTTPException(status_code=400, detail="허용되지 않는 파일명")
        # 최종 경로 계산
        reports_dir = Path("data/reports")
        target = (reports_dir / filename).resolve()
        # reports_dir 내부인지 확인
        if reports_dir.resolve() not in target.parents and target != reports_dir.resolve():
            raise HTTPException(status_code=400, detail="잘못된 경로")
        if not target.exists():
            raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다")
        target.unlink(missing_ok=True)
        return {"status": "ok", "deleted": filename}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"보고서 삭제 오류: {e}")
        raise HTTPException(status_code=500, detail="보고서 삭제 중 오류")

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
        # 최근 7일간의 백업 통계 (당일 포함)
        daily_stats = []
        for i in range(7):
            day_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=i)
            day_end = day_start + timedelta(days=1)

            # 수량 통계
            day_backups = db.query(Backup).filter(
                Backup.created_at >= day_start,
                Backup.created_at < day_end
            ).count()

            day_successful = db.query(Backup).filter(
                Backup.created_at >= day_start,
                Backup.created_at < day_end,
                Backup.status == "completed"
            ).count()

            day_failed = db.query(Backup).filter(
                Backup.created_at >= day_start,
                Backup.created_at < day_end,
                Backup.status == "failed"
            ).count()

            # 평균 지표
            avg_duration = db.query(func.avg(Backup.duration_seconds)).filter(
                Backup.created_at >= day_start,
                Backup.created_at < day_end,
                Backup.duration_seconds.isnot(None)
            ).scalar() or 0

            avg_compression = db.query(func.avg(Backup.compression_ratio)).filter(
                Backup.created_at >= day_start,
                Backup.created_at < day_end,
                Backup.compression_ratio.isnot(None)
            ).scalar() or 0

            daily_stats.append({
                "date": day_start.strftime("%Y-%m-%d"),
                "total_backups": int(day_backups),
                "successful_backups": int(day_successful),
                "failed_backups": int(day_failed),
                "avg_duration_seconds": round(float(avg_duration), 2) if avg_duration else 0,
                "avg_compression_ratio": round(float(avg_compression), 2) if avg_compression else 0,
            })

        # 최근 백업 목록 (필요 필드만 직렬화)
        recent_backups_rows = db.query(Backup).order_by(
            Backup.created_at.desc()
        ).limit(10).all()
        recent_backups = [
            {
                "id": row.id,
                "database_id": row.database_id,
                "status": row.status,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in recent_backups_rows
        ]

        # 활성 데이터베이스 목록 (필요 필드만 직렬화)
        active_rows = db.query(Database).filter(Database.is_active == True).all()
        active_databases = [
            {
                "id": it.id,
                "name": it.name,
                "display_name": it.display_name,
                "environment": it.environment,
                "priority": it.priority,
                "connection_status": it.connection_status,
            }
            for it in active_rows
        ]

        return {
            "daily_statistics": daily_stats,
            "recent_backups": recent_backups,
            "active_databases": active_databases,
            "summary": {
                "total_databases": len(active_databases),
                "total_backups_week": sum(stat["total_backups"] for stat in daily_stats),
                "successful_backups_week": sum(stat["successful_backups"] for stat in daily_stats),
                "failed_backups_week": sum(stat["failed_backups"] for stat in daily_stats),
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
