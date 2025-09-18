"""
다중 DB 백업 엔진 V2 (어댑터 패턴 기반)
- PostgreSQL, MySQL, SQLite 지원
- 어댑터 패턴으로 DB별 최적화된 백업 전략
- 공통 후처리 (압축/암호화/체크섬) 지원

주의:
- 기존 BackupEngine을 대체하는 새로운 구현
- 어댑터 패턴과 후처리 모듈을 활용
- Windows/Unix 환경 모두 동작
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple, Any

from app.config import settings, get_config_manager
from app.database import (
    SessionLocal,
    Database,
    Backup,
    Notification
)
from app.core.notification_service import NotificationService
from app.core.backup_adapters import create_backup_adapter
from app.core.backup_postprocessor import backup_postprocessor


class BackupEngineV2:
    """어댑터 패턴 기반 백업 엔진"""

    def __init__(self):
        # 백업/로그/임시 디렉터리 보장 생성
        Path(settings.BACKUP_BASE_PATH).mkdir(parents=True, exist_ok=True)
        Path(settings.TEMP_PATH).mkdir(parents=True, exist_ok=True)
        
        # 로거 설정
        self.logger = logging.getLogger(__name__)
        
        # 전역 동시 실행 제한(세마포어) 초기화
        if not hasattr(BackupEngineV2, "_sema"):
            BackupEngineV2._sema = threading.Semaphore(self._get_max_parallel_jobs())

    def _get_max_parallel_jobs(self) -> int:
        """최대 병렬 백업 작업 수 반환"""
        try:
            cm = get_config_manager()
            app_settings = cm.load_app_settings() or {}
            backup_settings = app_settings.get('backup', {})
            return int(backup_settings.get('max_parallel_jobs', 2))
        except Exception:
            return 2

    def run_backup(self, database_id: str, backup_id: str) -> None:
        """백업 실행 메인 함수 (어댑터 패턴 기반)
        - 새로운 DB 세션을 생성하여 메타데이터 갱신
        - 상태: pending -> running -> completed/failed
        - DB 타입별 최적화된 백업 전략 적용
        """
        db_session = SessionLocal()
        try:
            backup: Backup = db_session.query(Backup).filter(Backup.id == backup_id).first()
            target_db: Database = db_session.query(Database).filter(Database.id == database_id).first()
            if not backup or not target_db:
                return

            # 상태 running 전환
            backup.status = 'running'
            backup.started_at = datetime.utcnow()
            db_session.commit()

            # 출력 파일 경로/이름 생성: backups/<db_name>/<timestamp>_<backup_id>.<ext>
            ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            db_dir = Path(settings.BACKUP_BASE_PATH) / target_db.database_name
            db_dir.mkdir(parents=True, exist_ok=True)
            
            # DB 타입별 파일 확장자 결정
            file_ext = self._get_backup_file_extension(target_db.db_type)
            backup_path = db_dir / f"{ts}_{backup_id}.{file_ext}"

            # TODO: password_encrypted 복호화 로직 적용 (현재는 평문으로 가정)
            password = target_db.password_encrypted

            # 어댑터 기반 백업 실행
            success, error_msg, backup_metadata = self._run_backup_with_adapter(
                target_db, backup_path, password
            )
            
            if not success:
                raise RuntimeError(f"백업 실행 실패: {error_msg}")

            # 후처리 (압축/암호화/체크섬) 적용
            final_path, postprocess_metadata = self._apply_postprocessing(
                backup_path, db_dir
            )

            # 메타데이터 통합 및 갱신
            self._update_backup_metadata(
                backup, target_db, final_path, backup_metadata, postprocess_metadata
            )
            
            db_session.commit()
            
            # 성공/경고 알림 훅
            try:
                self._notify_on_success_or_warn(db_session, target_db.id, backup)
            except Exception:
                pass

        except Exception as e:
            # 실패 처리
            backup = db_session.query(Backup).filter(Backup.id == backup_id).first()
            if backup:
                backup.status = 'failed'
                backup.error_message = str(e)
                backup.completed_at = datetime.utcnow()
                if backup.started_at and backup.completed_at:
                    backup.duration_seconds = int((backup.completed_at - backup.started_at).total_seconds())
                db_session.commit()
                
                # 실패 알림 훅
                try:
                    self._notify_backup_failed(db_session, target_db.id if 'target_db' in locals() and target_db else None, backup.id, backup.error_message)
                except Exception:
                    pass
        finally:
            db_session.close()

    # ========================================
    # 어댑터 기반 백업 헬퍼 메서드들
    # ========================================
    
    def _get_backup_file_extension(self, db_type: str) -> str:
        """DB 타입별 백업 파일 확장자 반환"""
        db_type = db_type.lower().strip()
        if db_type == "postgresql":
            return "sql"
        elif db_type == "mysql":
            return "sql"
        elif db_type == "sqlite":
            return "db"
        else:
            return "backup"
    
    def _run_backup_with_adapter(
        self, 
        target_db: Database, 
        backup_path: Path, 
        password: Optional[str]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """어댑터를 사용한 백업 실행"""
        try:
            # 백업 어댑터 생성
            adapter = create_backup_adapter(target_db.db_type, target_db.id)
            
            # 백업 옵션 구성 (DB별로 다를 수 있음)
            backup_options = self._get_backup_options(target_db.db_type)
            
            # 백업 실행
            success, error_msg, metadata = adapter.run_backup(
                host=target_db.host,
                port=target_db.port,
                dbname=target_db.database_name,
                user=target_db.username,
                password=password,
                output_path=backup_path,
                options=backup_options
            )
            
            return success, error_msg, metadata
            
        except Exception as e:
            return False, f"어댑터 백업 오류: {str(e)}", {}
    
    def _get_backup_options(self, db_type: str) -> Dict[str, Any]:
        """DB 타입별 백업 옵션 반환"""
        db_type = db_type.lower().strip()
        
        if db_type == "postgresql":
            return {
                "format": "custom",
                "compress": 6,
                "verbose": True,
                "no_owner": True,
                "no_privileges": False,
            }
        elif db_type == "mysql":
            return {
                "single_transaction": True,
                "routines": True,
                "triggers": True,
                "events": True,
                "add_drop_table": True,
            }
        elif db_type == "sqlite":
            return {
                "method": "backup_api",
                "vacuum": True,
                "wal_checkpoint": True,
                "verify_integrity": True,
            }
        else:
            return {}
    
    def _apply_postprocessing(
        self, 
        backup_path: Path, 
        output_dir: Path
    ) -> Tuple[Path, Dict[str, Any]]:
        """백업 파일 후처리 (압축/암호화/체크섬) 적용"""
        try:
            # 압축/암호화 설정 가져오기
            comp_algo, comp_level = self._get_compression_settings()
            encrypt_enabled = settings.DEFAULT_ENCRYPTION
            
            # 후처리 실행
            success, final_path_str, metadata = backup_postprocessor.process_backup_file(
                input_path=backup_path,
                output_dir=output_dir,
                compress=True,
                compression_type=comp_algo,
                compression_level=comp_level,
                encrypt=encrypt_enabled,
                calculate_checksum=True,
                checksum_algorithm="sha256",
                cleanup_intermediate=True,
            )
            
            if not success:
                raise RuntimeError(f"후처리 실패: {final_path_str}")
            
            return Path(final_path_str), metadata
            
        except Exception as e:
            # 후처리 실패 시 원본 파일 반환
            self.logger.warning(f"후처리 실패, 원본 파일 사용: {e}")
            return backup_path, {}
    
    def _get_compression_settings(self) -> Tuple[str, int]:
        """압축 설정 반환 (알고리즘, 레벨)"""
        try:
            cm = get_config_manager()
            app_settings = cm.load_app_settings() or {}
            backup_settings = app_settings.get('backup', {})
            
            # 사용 가능한 압축 도구 확인
            available_tools = backup_postprocessor.get_available_compression_tools()
            
            # 우선순위: zstd > lz4 > gzip
            preferred_order = ['zstd', 'lz4', 'gzip']
            compression_algo = 'gzip'  # 기본값
            
            for tool in preferred_order:
                if available_tools.get(tool, False):
                    compression_algo = tool
                    break
            
            # 설정에서 명시적으로 지정된 경우 우선 사용
            config_algo = backup_settings.get('compression_algorithm', '').lower()
            if config_algo in available_tools and available_tools[config_algo]:
                compression_algo = config_algo
            
            compression_level = int(backup_settings.get('compression_level', 6))
            return compression_algo, compression_level
            
        except Exception:
            return 'gzip', 6
    
    def _update_backup_metadata(
        self,
        backup: Backup,
        target_db: Database,
        final_path: Path,
        backup_metadata: Dict[str, Any],
        postprocess_metadata: Dict[str, Any]
    ) -> None:
        """백업 메타데이터 업데이트"""
        try:
            # 기본 메타데이터
            backup.file_path = str(final_path)
            backup.file_size = final_path.stat().st_size if final_path.exists() else 0
            backup.status = 'completed'
            backup.completed_at = datetime.utcnow()
            
            if backup.started_at and backup.completed_at:
                backup.duration_seconds = int((backup.completed_at - backup.started_at).total_seconds())
            
            # 백업 도구별 메타데이터
            if "backup_tool" in backup_metadata:
                if target_db.db_type.lower() == "postgresql":
                    backup.pg_dump_version = backup_metadata.get("backup_tool", "")
            
            # 후처리 메타데이터
            if postprocess_metadata:
                backup.is_encrypted = postprocess_metadata.get("processing_steps", {}).get("encrypted", False)
                backup.checksum = postprocess_metadata.get("checksum", "")
                
                # 압축 관련 메타데이터
                if "compressed_size_bytes" in postprocess_metadata:
                    backup.compressed_size = postprocess_metadata["compressed_size_bytes"]
                    original_size = postprocess_metadata.get("original_size_bytes", 0)
                    if original_size > 0:
                        ratio = (postprocess_metadata["compressed_size_bytes"] / original_size) * 100
                        backup.compression_ratio = round(ratio, 2)
            
            # 체크섬이 없으면 직접 계산 (기존 방식 사용)
            if not backup.checksum and final_path.exists():
                backup.checksum = self._sha256(final_path)
                
        except Exception as e:
            self.logger.error(f"메타데이터 업데이트 오류: {e}")

    def _sha256(self, file_path: Path) -> str:
        """SHA-256 체크섬 계산 (기존 방식 유지)"""
        import hashlib
        try:
            hash_sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception:
            return ""

    # ========================================
    # 알림 관련 메서드들 (기존 방식 유지)
    # ========================================
    
    def _notify_on_success_or_warn(self, db_session, database_id: str, backup: Backup) -> None:
        """백업 성공/경고 알림"""
        try:
            notification_service = NotificationService()
            
            # 성공 알림
            title = f"백업 완료: {backup.id}"
            message = f"데이터베이스 백업이 성공적으로 완료되었습니다.\n"
            message += f"파일 크기: {backup.file_size} bytes\n"
            message += f"소요 시간: {backup.duration_seconds}초"
            
            notification = Notification(
                title=title,
                message=message,
                level="info",
                status="success",
                database_id=database_id,
                backup_id=backup.id
            )
            db_session.add(notification)
            db_session.commit()
            
            # 외부 알림 발송
            notification_service.send_notification(
                title=title,
                message=message,
                level="info"
            )
            
        except Exception as e:
            self.logger.error(f"성공 알림 오류: {e}")
    
    def _notify_backup_failed(self, db_session, database_id: Optional[str], backup_id: str, error_message: str) -> None:
        """백업 실패 알림"""
        try:
            notification_service = NotificationService()
            
            title = f"백업 실패: {backup_id}"
            message = f"데이터베이스 백업이 실패했습니다.\n오류: {error_message}"
            
            notification = Notification(
                title=title,
                message=message,
                level="error",
                status="failed",
                database_id=database_id,
                backup_id=backup_id
            )
            db_session.add(notification)
            db_session.commit()
            
            # 외부 알림 발송
            notification_service.send_notification(
                title=title,
                message=message,
                level="error"
            )
            
        except Exception as e:
            self.logger.error(f"실패 알림 오류: {e}")


# 전역 백업 엔진 V2 인스턴스
backup_engine_v2 = BackupEngineV2()
