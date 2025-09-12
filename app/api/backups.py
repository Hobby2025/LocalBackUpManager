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
from datetime import datetime
from pathlib import Path
import os

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

# -------------------------
# Phase 4.1: 트리거 엔드포인트
# -------------------------

@router.post("/database/{database_id}/base-backup", summary="베이스 백업 실행(pg_basebackup)")
async def trigger_base_backup(
    database_id: str,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None,
):
    """pg_basebackup 기반 베이스 백업을 실행합니다."""
    try:
        new_backup = create_backup_record(
            db,
            database_id=database_id,
            backup_type="base",
            status="pending",
        )

        if background_tasks is not None:
            background_tasks.add_task(BackupEngine().run_base_backup, database_id, new_backup.id)
        logger.info(f"베이스 백업 시작(백그라운드): {new_backup.id}")

        return {"message": "베이스 백업이 시작되었습니다.", "backup_id": new_backup.id, "status": "pending"}
    except Exception as e:
        logger.error(f"베이스 백업 트리거 오류: {e}")
        raise HTTPException(status_code=500, detail="베이스 백업 트리거 중 오류")


@router.post("/database/{database_id}/incremental-backup", summary="증분 백업 실행(WAL 스냅샷)")
async def trigger_incremental_backup(
    database_id: str,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None,
):
    """WAL 아카이브를 tar.gz로 스냅샷하는 증분 백업을 실행합니다."""
    try:
        new_backup = create_backup_record(
            db,
            database_id=database_id,
            backup_type="incremental",
            status="pending",
        )

        if background_tasks is not None:
            background_tasks.add_task(BackupEngine().run_incremental_backup, database_id, new_backup.id)
        logger.info(f"증분 백업 시작(백그라운드): {new_backup.id}")

        return {"message": "증분 백업이 시작되었습니다.", "backup_id": new_backup.id, "status": "pending"}
    except Exception as e:
        logger.error(f"증분 백업 트리거 오류: {e}")
        raise HTTPException(status_code=500, detail="증분 백업 트리거 중 오류")


@router.post("/wal/maintenance", summary="WAL 아카이브 인덱싱/정리 실행")
async def wal_maintenance():
    """WAL 아카이브 디렉터리 인덱싱 및 보존 정책에 따른 정리를 수행합니다."""
    try:
        engine = BackupEngine()
        archive_dir = engine._get_wal_archive_dir()  # 설정 기반 경로
        archive_dir.mkdir(parents=True, exist_ok=True)
        engine.index_wal_archive(archive_dir)
        engine.cleanup_wal_archive(archive_dir)
        return {"message": "WAL 인덱싱/정리를 수행했습니다.", "archive_dir": str(archive_dir)}
    except Exception as e:
        logger.error(f"WAL 유지보수 오류: {e}")
        raise HTTPException(status_code=500, detail="WAL 유지보수 중 오류")


@router.post("/pitr/plan", summary="PITR 복구 계획 산출(베이스/필요 WAL 목록)")
async def pitr_plan(
    payload: dict,
    db: Session = Depends(get_db),
):
    """대상 시각 기준으로 적합한 베이스 백업과 필요한 WAL 파일 후보를 제시합니다.
    요청 예시: {"database_id": "...", "target_time": "2025-09-12T00:00:00Z"}
    """
    try:
        database_id = payload.get("database_id")
        target_time_iso = payload.get("target_time")
        if not database_id or not target_time_iso:
            raise HTTPException(status_code=400, detail="database_id와 target_time이 필요합니다.")

        # ISO 파싱(UTC 가정, Z 허용)
        t_iso = target_time_iso.replace("Z", "+00:00")
        try:
            target_dt = datetime.fromisoformat(t_iso)
        except Exception:
            raise HTTPException(status_code=400, detail="target_time 형식이 올바르지 않습니다(ISO 8601)")

        # 1) 대상 DB의 베이스 백업 중 target 이전 최신 레코드 탐색
        base = (
            db.query(Backup)
            .filter(Backup.database_id == database_id)
            .filter(Backup.backup_type.in_(["base", "full"]))
            .filter(Backup.status == "completed")
            .filter(Backup.completed_at <= target_dt)
            .order_by(Backup.completed_at.desc())
            .first()
        )
        if not base:
            return {"message": "대상 시각 이전의 베이스 백업이 없습니다.", "plan": None}

        # 2) WAL 후보 목록: archive_dir에서 base.completed_at ~ target_dt 사이 파일 수집(날짜 폴더 기반)
        engine = BackupEngine()
        archive_dir = engine._get_wal_archive_dir()
        wal_files = []
        # 날짜 범위 스캔(하루 여유 포함)
        day_cursor = base.completed_at.date()
        end_day = target_dt.date()
        while day_cursor <= end_day:
            day_path = archive_dir / day_cursor.strftime("%Y%m%d")
            if day_path.is_dir():
                for fp in day_path.glob("*"):
                    try:
                        mtime = datetime.utcfromtimestamp(fp.stat().st_mtime)
                        if base.completed_at <= mtime <= target_dt:
                            wal_files.append(str(fp))
                    except Exception:
                        continue
            # 다음 날로 이동
            from datetime import timedelta as _td
            day_cursor = day_cursor + _td(days=1)

        return {
            "plan": {
                "base_backup": {
                    "backup_id": base.id,
                    "completed_at": base.completed_at.isoformat() if base.completed_at else None,
                    "file_path": base.file_path,
                },
                "wal_archive_dir": str(archive_dir),
                "wal_files": wal_files,
                "target_time": target_dt.isoformat(),
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PITR 계획 산출 오류: {e}")
        raise HTTPException(status_code=500, detail="PITR 계획 산출 중 오류")

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
