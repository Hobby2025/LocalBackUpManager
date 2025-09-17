"""
백업 관리 API 라우터
백업 실행, 조회, 복원, 통계 기능
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from fastapi import UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from app.database import get_db, Backup, get_backups_by_database, create_backup_record
from app.core.backup_engine import BackupEngine  # 백업 엔진
from app.core.auth import require_roles
from datetime import datetime
from pathlib import Path
import os
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)
router = APIRouter()


def _serialize_backup(b: Backup) -> dict:
    """Backup ORM 객체를 안전한 dict로 직렬화
    - 압축 지표(compressed_size, compression_ratio) 포함
    - 날짜 필드는 ISO 문자열로 변환
    """
    return {
        "id": b.id,
        "database_id": b.database_id,
        "backup_type": b.backup_type,
        "status": b.status,
        "file_path": b.file_path,
        "file_size": b.file_size,
        "compressed_size": getattr(b, 'compressed_size', None),
        "compression_ratio": getattr(b, 'compression_ratio', None),
        "is_encrypted": b.is_encrypted,
        "checksum": b.checksum,
        "started_at": b.started_at.isoformat() if b.started_at else None,
        "completed_at": b.completed_at.isoformat() if b.completed_at else None,
        "duration_seconds": b.duration_seconds,
        "error_message": b.error_message,
        "pg_dump_version": b.pg_dump_version,
        "database_size": getattr(b, 'database_size', None),
        "created_at": b.created_at.isoformat() if getattr(b, 'created_at', None) else None,
        "updated_at": b.updated_at.isoformat() if getattr(b, 'updated_at', None) else None,
    }

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
        # 직렬화하여 반환
        return {
            "total": total,
            "backups": [_serialize_backup(b) for b in backups],
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
        return _serialize_backup(backup)
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


@router.get("/tools/compression-status", summary="압축 도구 가용성 점검")
async def compression_status():
    """시스템의 압축 도구(zstd, lz4) 사용 가능 여부와 현재 설정값을 반환합니다."""
    try:
        zstd_ok = shutil.which('zstd') is not None
        lz4_ok = shutil.which('lz4') is not None
        # gzip은 표준 라이브러리로 항상 사용 가능하다고 간주
        from app.config import settings
        # compression_level은 settings.yaml에서 읽는 값이므로 엔진 유틸을 재사용하지 않고 기본값만 노출
        level = 3
        try:
            from app.config import get_config_manager
            cm = get_config_manager()
            app_settings = cm.load_app_settings() or {}
            level = int(((app_settings.get('backup') or {}).get('compression_level')) or 3)
        except Exception:
            pass
        return {
            "gzip": True,
            "zstd": zstd_ok,
            "lz4": lz4_ok,
            "default_compression": getattr(settings, 'DEFAULT_COMPRESSION', 'gzip'),
            "compression_level": level,
        }
    except Exception as e:
        logger.error(f"압축 도구 점검 오류: {e}")
        raise HTTPException(status_code=500, detail="압축 도구 점검 중 오류")


# -------------------------
# 벤치마크 리포트 업로드/열람 (간단)
# -------------------------

REPORT_DIR = Path("data/reports")

@router.get("/benchmarks", summary="벤치마크 리포트 목록")
async def list_benchmarks():
    """data/reports 디렉터리의 CSV/JSON 리포트를 나열합니다."""
    try:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        items = []
        for fp in REPORT_DIR.glob("*"):
            if fp.suffix.lower() not in [".csv", ".json"]:
                continue
            try:
                st = fp.stat()
                items.append({
                    "name": fp.name,
                    "size": st.st_size,
                    "modified": datetime.fromtimestamp(st.st_mtime).isoformat(),
                    "path": f"/static/reports/{fp.name}"  # 프런트에서 접근용(정적 마운트 권장)
                })
            except Exception:
                continue
        # 최신 수정 순으로 정렬
        items.sort(key=lambda x: x["modified"], reverse=True)
        return {"reports": items}
    except Exception as e:
        logger.error(f"리포트 목록 오류: {e}")
        raise HTTPException(status_code=500, detail="리포트 목록 조회 중 오류")


@router.post("/benchmarks", summary="벤치마크 리포트 업로드")
async def upload_benchmark(file: UploadFile = File(...)):
    """CSV/JSON 리포트 파일 업로드"""
    try:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        ext = Path(file.filename).suffix.lower()
        if ext not in [".csv", ".json"]:
            raise HTTPException(status_code=400, detail="csv 또는 json 파일만 허용됩니다.")
        # 파일명 충돌 방지용 타임스탬프 접미사 부여
        ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        safe_name = Path(file.filename).stem[:80].replace('/', '_').replace('\\', '_')
        dst = REPORT_DIR / f"{safe_name}_{ts}{ext}"
        with open(dst, 'wb') as out:
            out.write(await file.read())
        st = dst.stat()
        return {
            "message": "업로드 완료",
            "name": dst.name,
            "size": st.st_size,
            "modified": datetime.fromtimestamp(st.st_mtime).isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"리포트 업로드 오류: {e}")
        raise HTTPException(status_code=500, detail="리포트 업로드 중 오류")

@router.post("/{backup_id}/cancel", summary="백업 취소")
async def cancel_backup(
    backup_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """실행 중인 백업을 취소합니다. (admin 권한 필요)"""
    # 관리자 권한 검사
    if not require_roles(request, ("admin",)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다."
        )
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
        # 기본 통계 계산
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

        # 평균 크기/소요시간/압축률, 최근 백업
        last = db.query(Backup).filter(Backup.database_id == database_id).order_by(Backup.created_at.desc()).first()
        sizes = [b.file_size for b in db.query(Backup).filter(Backup.database_id == database_id, Backup.file_size != None).all()]
        durations = [b.duration_seconds for b in db.query(Backup).filter(Backup.database_id == database_id, Backup.duration_seconds != None).all()]
        ratios = [b.compression_ratio for b in db.query(Backup).filter(Backup.database_id == database_id, Backup.compression_ratio != None).all()]

        def _avg(arr):
            return round(sum(arr) / len(arr), 2) if arr else 0

        return {
            "database_id": database_id,
            "total_backups": total_backups,
            "successful_backups": successful_backups,
            "failed_backups": failed_backups,
            "success_rate": round(success_rate, 2),
            "statistics": {
                "avg_backup_size": _avg(sizes),
                "avg_duration": _avg(durations),
                "avg_compression_ratio": _avg(ratios),
                "last_backup": _serialize_backup(last) if last else None,
            }
        }
        
    except Exception as e:
        logger.error(f"백업 통계 조회 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="백업 통계 조회 중 오류가 발생했습니다."
        )
