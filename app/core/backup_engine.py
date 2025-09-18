"""
다중 DB 백업 엔진 (어댑터 패턴 기반)
- PostgreSQL, MySQL, SQLite 지원
- 어댑터 패턴으로 DB별 최적화된 백업 전략
- 공통 후처리 (압축/암호화/체크섬) 지원

주의:
- 변수명은 변경하지 않음
- 외부 의존성 추가 없이 표준 라이브러리/기존 패키지만 사용
- Windows/Unix 모두 동작하도록 경로 처리
"""

import os
import subprocess
import hashlib
import shutil
import tarfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List
import logging
import shutil as _shutil
import threading

from app.config import settings, get_config_manager
from app.database import (
    SessionLocal,
    Database,
    Backup,
)
from app.database import Notification
from app.core.notification_service import NotificationService
from app.core.backup_adapters import create_backup_adapter
from app.core.backup_postprocessor import backup_postprocessor

# 암호화에 필요한 모듈 (requirements.txt의 cryptography 사용)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import secrets

# 암호화 포맷 매직 헤더
# 포맷: [MAGIC(4='LBM1')][key_id_len(1)][key_id][nonce(12)][ciphertext+tag]
MAGIC_V1 = b"LBM1"


class BackupEngine:
    """기본 백업 엔진 클래스"""

    def __init__(self):
        # 백업/로그/임시 디렉터리 보장 생성
        Path(settings.BACKUP_BASE_PATH).mkdir(parents=True, exist_ok=True)
        Path(settings.TEMP_PATH).mkdir(parents=True, exist_ok=True)
        # 로거 설정
        self.logger = logging.getLogger(__name__)
        # 전역 동시 실행 제한(세마포어) 초기화 - 프로세스 내에서만 유효
        if not hasattr(BackupEngine, "_sema"):
            BackupEngine._sema = threading.Semaphore(self._get_max_parallel_jobs())

    # -------- 보안 키 로딩 유틸 --------
    def _get_active_encryption_key(self) -> Optional[str]:
        """settings.yaml의 security.encryption 설정에서 활성 키를 조회하여 반환
        - 구조: security.encryption.active_key_id, security.encryption.keys: [{id, key}]
        - key는 32자 문자열(UTF-8) 권장
        - 유효하지 않으면 None 반환
        """
        try:
            cm = get_config_manager()
            app_settings = cm.load_app_settings() or {}
            sec = (app_settings.get('security') or {})
            enc = (sec.get('encryption') or {})
            active_id = (enc.get('active_key_id') or '').strip()
            keys = enc.get('keys') or []
            if not active_id or not isinstance(keys, list):
                return None
            for item in keys:
                try:
                    if (item or {}).get('id') == active_id:
                        k = (item or {}).get('key')
                        if isinstance(k, str) and len(k) == 32:
                            return k
                except Exception:
                    continue
        except Exception:
            return None
        return None

    def _get_active_encryption_key_info(self) -> Optional[tuple[str, str]]:
        """활성 키의 (key_id, key_str) 튜플 반환. 없으면 None
        - 키 문자열은 32자(UTF-8)로 가정
        """
        try:
            cm = get_config_manager()
            app_settings = cm.load_app_settings() or {}
            sec = (app_settings.get('security') or {})
            enc = (sec.get('encryption') or {})
            active_id = (enc.get('active_key_id') or '').strip()
            keys = enc.get('keys') or []
            if not active_id or not isinstance(keys, list):
                return None
            for item in keys:
                try:
                    if (item or {}).get('id') == active_id:
                        k = (item or {}).get('key')
                        if isinstance(k, str) and len(k) == 32:
                            return active_id, k
                except Exception:
                    continue
        except Exception:
            return None
        return None

    # ==========================
    # Phase 4: WAL/증분/PITR 스켈레톤
    # ==========================
    def enable_wal_archiving(self, archive_dir: Optional[Path] = None) -> None:
        """WAL 아카이빙 활성화(스켈레톤)
        - 실제로는 PostgreSQL 서버의 postgresql.conf / archive_command 설정이 필요함
        - 본 시스템에서는 WAL 보관 경로가 존재하는지만 보장하고, 상세 설정은 운영 가이드에 위임
        """
        try:
            # 설정에서 경로 읽기
            wal_dir = archive_dir or Path("./data/wal_archive")
            wal_dir.mkdir(parents=True, exist_ok=True)
            # 실제 archive_command 설정은 DB 서버 측 작업이므로 여기서는 로깅만 수행
            self.logger.info("WAL 아카이빙 경로 준비 완료: %s", str(wal_dir))
        except Exception as e:
            self.logger.error("WAL 아카이빙 경로 준비 실패: %s", e)

    def perform_base_backup(self, target_db: Database) -> Path:
        """베이스 백업 수행(스켈레톤)
        - pg_basebackup 등을 사용하여 베이스 백업을 생성
        - 현재는 디렉터리만 생성하는 스텁으로 제공
        반환값: 베이스 백업이 저장된 디렉터리 경로
        """
        ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        base_dir = Path(settings.BACKUP_BASE_PATH) / target_db.database_name / f"base_{ts}"
        base_dir.mkdir(parents=True, exist_ok=True)
        # 실제 pg_basebackup 실행
        try:
            start = datetime.utcnow()
            self._run_pg_basebackup(target_db, base_dir, password=target_db.password_encrypted)
            duration = int((datetime.utcnow() - start).total_seconds())
            self.logger.info("pg_basebackup 완료: dir=%s duration=%ss", str(base_dir), duration)
        except Exception as e:
            # 실패 시 디렉터리 정리(비어 있으면)
            try:
                if base_dir.exists() and not any(base_dir.iterdir()):
                    base_dir.rmdir()
            except Exception:
                pass
            raise
        return base_dir

    def _run_pg_basebackup(self, db: Database, dest_dir: Path, password: Optional[str]) -> None:
        """pg_basebackup 실행 유틸
        - 기본 플래그: 포맷 plain(-Fp), WAL 동시 수집(-X fetch), 체크포인트 fast(-c fast)
        - 환경 변수 PGPASSWORD 사용
        """
        env = os.environ.copy()
        if password:
            env['PGPASSWORD'] = password
        cmd = [
            'pg_basebackup',
            '-h', str(db.host),
            '-p', str(db.port),
            '-U', str(db.username),
            '-D', str(dest_dir),
            '-F', 'p',
            '-X', 'fetch',
            '-c', 'fast',
        ]
        completed = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if completed.returncode != 0:
            self.logger.error("pg_basebackup 실패: %s", completed.stderr)
            raise RuntimeError(f"pg_basebackup 실패: {completed.stderr}")

    def run_base_backup(self, database_id: str, backup_id: str) -> None:
        """베이스 백업 실행(전체 파일 기반) 및 메타데이터 기록
        - pg_basebackup으로 디렉터리를 생성한 뒤 tar.gz로 보관
        - 암호화 옵션 적용
        """
        db_session = SessionLocal()
        try:
            # 동시 실행 제한 진입
            BackupEngine._sema.acquire()
            backup: Backup = db_session.query(Backup).filter(Backup.id == backup_id).first()
            target_db: Database = db_session.query(Database).filter(Database.id == database_id).first()
            if not backup or not target_db:
                return

            backup.status = 'running'
            backup.started_at = datetime.utcnow()
            db_session.commit()

            # 베이스 백업 수행
            base_dir = self.perform_base_backup(target_db)

            # tar 아카이브 생성(무압축) → 이후 설정에 따라 압축 적용
            ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            db_dir = Path(settings.BACKUP_BASE_PATH) / target_db.database_name
            db_dir.mkdir(parents=True, exist_ok=True)
            tar_path = db_dir / f"base_{ts}_{backup_id}.tar"
            with tarfile.open(tar_path, 'w') as tar:
                for p in base_dir.rglob('*'):
                    try:
                        tar.add(p, arcname=str(p.relative_to(base_dir)))
                    except Exception:
                        continue

            # 필요 시 원본 디렉터리 정리(공간 절약)
            try:
                for p in sorted(base_dir.rglob('*'), reverse=True):
                    if p.is_file():
                        p.unlink(missing_ok=True)
                base_dir.rmdir()
            except Exception:
                pass

            # 압축 적용(gzip/zstd/lz4)
            comp_algo, comp_level = self._get_compression_settings()
            final_path = self._compress_file(tar_path, comp_algo, comp_level)
            try:
                if tar_path.exists():
                    tar_path.unlink()
            except Exception:
                pass
            encrypted = False
            if settings.DEFAULT_ENCRYPTION:
                enc_path = Path(str(final_path) + '.enc')
                key_info = self._get_active_encryption_key_info()
                if not key_info:
                    raise ValueError("활성 암호화 키가 설정되어 있지 않습니다(security.encryption).")
                key_id, key_str = key_info
                # 개선된 포맷으로 암호화 (매직/키ID 포함)
                self._aes_gcm_encrypt_file_v2(final_path, enc_path, key_id, key_str)
                try:
                    final_path.unlink(missing_ok=True)
                except TypeError:
                    if final_path.exists():
                        final_path.unlink()
                final_path = enc_path
                encrypted = True

            file_size = final_path.stat().st_size
            checksum = self._sha256(final_path)

            # 메타데이터 갱신
            backup.file_path = str(final_path)
            backup.file_size = file_size
            backup.is_encrypted = encrypted
            backup.status = 'completed'
            backup.completed_at = datetime.utcnow()
            if backup.started_at and backup.completed_at:
                backup.duration_seconds = int((backup.completed_at - backup.started_at).total_seconds())
            # pg_dump_version 필드 재사용(버전 기록용)
            ver = self._pg_dump_version()
            if ver:
                backup.pg_dump_version = ver
            backup.checksum = checksum
            db_session.commit()
            # 성공/경고 알림 훅
            try:
                self._notify_on_success_or_warn(db_session, target_db.id, backup)
            except Exception:
                pass

        except Exception as e:
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
            # 세마포어 해제
            try:
                BackupEngine._sema.release()
            except Exception:
                pass
            db_session.close()

    def run_incremental_backup(self, database_id: str, backup_id: str) -> None:
        """증분 백업 실행(스켈레톤)
        - WAL 아카이빙 기반으로 변경분만 수집/보관
        - 메타데이터 모델 정합성 검토 후 실제 구현 예정
        """
        self.logger.info("증분 백업 시작 - database_id=%s backup_id=%s", database_id, backup_id)
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

            # WAL 아카이브 경로 준비(설정 파일 우선)
            archive_dir = self._get_wal_archive_dir()
            archive_dir.mkdir(parents=True, exist_ok=True)

            # WAL 인덱싱 및 정리 실행
            self.index_wal_archive(archive_dir)
            self.cleanup_wal_archive(archive_dir)

            # 스냅샷 대상 파일 선별: started_at 기준 최근 WAL 파일 수집(보수적으로 최근 24h)
            since = (backup.started_at or datetime.utcnow()) - timedelta(days=1)
            wal_files = self._collect_wal_files_since(archive_dir, since)

            # WAL 스냅샷 tar 생성(무압축) → 이후 설정에 따라 압축 적용
            ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            db_dir = Path(settings.BACKUP_BASE_PATH) / target_db.database_name
            db_dir.mkdir(parents=True, exist_ok=True)
            tar_path = db_dir / f"wal_{ts}_{backup_id}.tar"
            with tarfile.open(tar_path, 'w') as tar:
                for fp in wal_files:
                    try:
                        tar.add(fp, arcname=str(fp.relative_to(archive_dir)))
                    except Exception:
                        continue

            # 압축 적용(gzip/zstd/lz4)
            comp_algo, comp_level = self._get_compression_settings()
            final_path = self._compress_file(tar_path, comp_algo, comp_level)
            try:
                if tar_path.exists():
                    tar_path.unlink()
            except Exception:
                pass

            # 암호화 옵션 적용
            encrypted = False
            if settings.DEFAULT_ENCRYPTION:
                enc_path = Path(str(final_path) + '.enc')
                # 활성 암호화 키 조회 (settings.yaml의 security.encryption)
                key_info = self._get_active_encryption_key_info()
                if not key_info:
                    raise ValueError("활성 암호화 키가 설정되어 있지 않습니다(security.encryption).")
                key_id, key_str = key_info
                self._aes_gcm_encrypt_file_v2(final_path, enc_path, key_id, key_str)
                try:
                    final_path.unlink(missing_ok=True)
                except TypeError:
                    if final_path.exists():
                        final_path.unlink()
                final_path = enc_path
                encrypted = True

            file_size = final_path.stat().st_size
            checksum = self._sha256(final_path)

            # 메타데이터 갱신
            backup.file_path = str(final_path)
            backup.file_size = file_size
            backup.is_encrypted = encrypted
            backup.status = 'completed'
            backup.completed_at = datetime.utcnow()
            if backup.started_at and backup.completed_at:
                backup.duration_seconds = int((backup.completed_at - backup.started_at).total_seconds())
            backup.checksum = checksum
            # pg_dump_version 필드가 있다면 재사용 (증분은 pg_basebackup와 무관하지만 필드 존재 대비)
            ver = self._pg_dump_version()
            if ver:
                backup.pg_dump_version = ver
            db_session.commit()
            # 성공/경고 알림 훅
            try:
                self._notify_on_success_or_warn(db_session, target_db.id, backup)
            except Exception:
                pass

        except Exception as e:
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

    def index_wal_archive(self, archive_dir: Path) -> None:
        """WAL 아카이브 디렉터리 인덱싱(간단 정리)
        - 파일 mtime 기준으로 YYYYMMDD 하위 폴더로 이동해 날짜별로 정리
        """
        try:
            for fp in list(archive_dir.glob('*')):
                if fp.is_file():
                    day = datetime.utcfromtimestamp(fp.stat().st_mtime).strftime('%Y%m%d')
                    day_dir = archive_dir / day
                    day_dir.mkdir(parents=True, exist_ok=True)
                    try:
                        target = day_dir / fp.name
                        if not target.exists():
                            fp.replace(target)
                    except Exception:
                        continue
        except Exception as e:
            self.logger.error("WAL 인덱싱 실패: %s", e)

    def cleanup_wal_archive(self, archive_dir: Path) -> None:
        """보존 정책(keep_days) 기반 WAL 정리"""
        try:
            keep_days = self._get_wal_keep_days()
            cutoff = datetime.utcnow() - timedelta(days=keep_days)
            for day_dir in archive_dir.glob('*'):
                if day_dir.is_dir():
                    try:
                        day = datetime.strptime(day_dir.name, '%Y%m%d')
                        if day.date() < cutoff.date():
                            # 너무 과감한 삭제를 피하기 위해 디렉토리 내 파일만 삭제, 빈 폴더는 남김
                            for fp in day_dir.glob('*'):
                                if fp.is_file():
                                    fp.unlink(missing_ok=True)
                    except Exception:
                        continue
        except Exception as e:
            self.logger.error("WAL 정리 실패: %s", e)

    def _collect_wal_files_since(self, archive_dir: Path, since: datetime) -> List[Path]:
        """지정 시각 이후 수정된 WAL 파일 목록 수집"""
        files: List[Path] = []
        for day_dir in archive_dir.glob('*'):
            if day_dir.is_dir():
                for fp in day_dir.glob('*'):
                    try:
                        if fp.is_file() and datetime.utcfromtimestamp(fp.stat().st_mtime) >= since:
                            files.append(fp)
                    except Exception:
                        continue
        return files

    # -------- 설정 로딩 유틸 --------
    def _get_wal_settings(self) -> dict:
        """settings.yaml의 backup.wal 섹션 로드(없으면 기본값 반환)"""
        cm = get_config_manager()
        app_settings = cm.load_app_settings() or {}
        wal = ((app_settings.get('backup') or {}).get('wal') or {})
        return {
            'archive_dir': wal.get('archive_dir') or './data/wal_archive',
            'keep_days': int(wal.get('keep_days') or 7),
        }

    def _get_wal_archive_dir(self) -> Path:
        s = self._get_wal_settings()
        # 환경변수로 오버라이드 허용
        env_dir = os.getenv('WAL_ARCHIVE_DIR')
        return Path(env_dir or s['archive_dir'])

    def _get_wal_keep_days(self) -> int:
        s = self._get_wal_settings()
        return int(s['keep_days'])

    # -------- 압축 설정/실행 유틸 --------
    def _get_compression_settings(self) -> tuple[str, int]:
        """압축 알고리즘/레벨 설정값 반환
        - 알고리즘: settings.DEFAULT_COMPRESSION (gzip|zstd|lz4)
        - 레벨: config settings.yaml의 backup.compression_level (기본 3)
        """
        algo = (getattr(settings, 'DEFAULT_COMPRESSION', 'gzip') or 'gzip').lower()
        try:
            cm = get_config_manager()
            app_settings = cm.load_app_settings() or {}
            level = int(((app_settings.get('backup') or {}).get('compression_level')) or 3)
        except Exception:
            level = 3
        return algo, min(max(level, 1), 9)

    def _compress_file(self, src: Path, algo: str, level: int) -> Path:
        """파일 압축(gzip/zstd/lz4). 외부 도구 없으면 gzip으로 폴백.
        반환: 생성된 압축 파일 경로
        """
        try:
            if algo == 'zstd' and _shutil.which('zstd'):
                dst = Path(str(src) + '.zst') if src.suffix != '.zst' else src
                cmd = ['zstd', f'-{level}', '-T0', '-f', str(src), '-o', str(dst)]
                c = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if c.returncode != 0:
                    self.logger.warning('zstd 실패, gzip으로 폴백: %s', c.stderr)
                else:
                    return dst
            if algo == 'lz4' and _shutil.which('lz4'):
                dst = Path(str(src) + '.lz4') if src.suffix != '.lz4' else src
                cmd = ['lz4', f'-{level}', '-f', str(src), str(dst)]
                c = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if c.returncode != 0:
                    self.logger.warning('lz4 실패, gzip으로 폴백: %s', c.stderr)
                else:
                    return dst
        except Exception as e:
            self.logger.warning('외부 압축 도구 실패: %s, gzip으로 폴백', e)
        # 기본: gzip
        dst = Path(str(src) + '.gz') if src.suffix != '.gz' else src
        self._gzip_compress_level(src, dst, level)
        return dst

    # -------- 알림 훅 --------
    def _notify_backup_failed(self, db_session, database_id: Optional[str], backup_id: Optional[str], error_message: Optional[str]):
        """백업 실패 시 critical 알림 전송 및 Notification 레코드 기록"""
        try:
            svc = NotificationService()
            # Notification 레코드 저장
            rec = Notification(
                database_id=database_id,
                backup_id=backup_id,
                notification_type='broadcast',
                level='critical',
                title='백업 실패',
                message=f'백업 실패: backup_id={backup_id}\n오류: {error_message or "알 수 없는 오류"}',
                status='pending',
                created_at=datetime.utcnow(),
            )
            db_session.add(rec)
            db_session.commit()
            db_session.refresh(rec)

            # 브로드캐스트 전송 (활성 채널 대상)
            res = svc.broadcast(title='백업 실패', message=f'백업 실패: backup_id={backup_id}\n오류: {error_message or "알 수 없는 오류"}')
            # 성공/실패 반영 (간단 판단: 하나라도 success면 sent로 간주)
            sent = any((v or {}).get('status') == 'success' for v in res.values() if isinstance(v, dict))
            rec.status = 'sent' if sent else 'failed'
            if sent:
                rec.sent_at = datetime.utcnow()
            else:
                # 대표 에러 메시지 수집
                details = [ (k, v.get('detail')) for k, v in res.items() if isinstance(v, dict) and v.get('status')=='error']
                if details:
                    rec.error_message = '; '.join([f'{k}:{d}' for k,d in details if d])
            db_session.commit()
        except Exception:
            # 알림 실패는 앱 동작에 영향 주지 않음
            pass

    def _notify_on_success_or_warn(self, db_session, database_id: Optional[str], backup: Backup) -> None:
        """백업 성공 시 규칙에 따른 성공/경고 알림 전송"""
        try:
            cm = get_config_manager()
            app_settings = cm.load_app_settings() or {}
            notif = (app_settings.get('notifications') or {})
            if not notif or not notif.get('enable'):
                return
            rules = (notif.get('rules') or {})
            notify_on_success = bool(rules.get('notify_on_success'))
            warn_on_thresholds = bool(rules.get('warn_on_thresholds'))
            thresholds = (rules.get('thresholds') or {})
            # 임계치 판정
            warnings: list[str] = []
            try:
                ratio_gt = thresholds.get('compression_ratio_percent_gt')
                if ratio_gt is not None and isinstance(backup.compression_ratio, (int, float)):
                    if backup.compression_ratio > float(ratio_gt):
                        warnings.append(f"압축률 임계 초과: {backup.compression_ratio}% > {ratio_gt}%")
            except Exception:
                pass
            try:
                dur_gt = thresholds.get('duration_seconds_gt')
                if dur_gt is not None and isinstance(backup.duration_seconds, int):
                    if backup.duration_seconds > int(dur_gt):
                        warnings.append(f"소요시간 임계 초과: {backup.duration_seconds}s > {dur_gt}s")
            except Exception:
                pass

            svc = NotificationService()
            # 경고 우선
            if warn_on_thresholds and warnings:
                title = '백업 경고(임계 초과)'
                msg = (
                    f"database_id={database_id}\n"
                    f"backup_id={backup.id}\n"
                    f"상세: " + '; '.join(warnings)
                )
                res = svc.broadcast(title=title, message=msg)
                # 기록(요약)
                rec = Notification(
                    database_id=database_id,
                    backup_id=backup.id,
                    notification_type='broadcast',
                    level='warning',
                    title=title,
                    message=msg,
                    status='sent' if any((v or {}).get('status')=='success' for v in res.values() if isinstance(v, dict)) else 'failed',
                    created_at=datetime.utcnow(),
                )
                if rec.status == 'sent':
                    rec.sent_at = datetime.utcnow()
                db_session.add(rec)
                db_session.commit()
                return

            # 성공 알림
            if notify_on_success:
                title = '백업 성공'
                msg = (
                    f"database_id={database_id}\n" 
                    f"backup_id={backup.id}\n" 
                    f"크기={backup.file_size}B, 압축률={backup.compression_ratio or '-'}%, 시간={backup.duration_seconds or '-'}s"
                )
                res = svc.broadcast(title=title, message=msg)
                rec = Notification(
                    database_id=database_id,
                    backup_id=backup.id,
                    notification_type='broadcast',
                    level='info',
                    title=title,
                    message=msg,
                    status='sent' if any((v or {}).get('status')=='success' for v in res.values() if isinstance(v, dict)) else 'failed',
                    created_at=datetime.utcnow(),
                )
                if rec.status == 'sent':
                    rec.sent_at = datetime.utcnow()
                db_session.add(rec)
                db_session.commit()
        except Exception:
            pass
            if algo == 'lz4' and _shutil.which('lz4'):
                dst = Path(str(src) + '.lz4') if src.suffix != '.lz4' else src
                cmd = ['lz4', f'-{level}', '-f', str(src), str(dst)]
                c = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if c.returncode != 0:
                    self.logger.warning('lz4 실패, gzip으로 폴백: %s', c.stderr)
                else:
                    return dst
        except Exception as e:
            self.logger.warning('외부 압축 도구 실패: %s, gzip으로 폴백', e)
        # 기본: gzip
        dst = Path(str(src) + '.gz') if src.suffix != '.gz' else src
        self._gzip_compress_level(src, dst, level)
        return dst

    def _gzip_compress_level(self, src: Path, dst: Path, level: int) -> None:
        """gzip 압축(레벨 적용)
        - 표준 라이브러리 gzip을 사용하며 compresslevel을 설정
        """
        import gzip
        with open(src, 'rb') as f_in:
            with gzip.open(dst, 'wb', compresslevel=min(max(level, 1), 9)) as f_out:
                shutil.copyfileobj(f_in, f_out)

    def _get_max_parallel_jobs(self) -> int:
        """최대 동시 실행 잡 개수 읽기(settings.yaml의 backup.max_parallel_jobs)
        - 읽기 실패 시 3으로 폴백
        """
        try:
            cm = get_config_manager()
            app_settings = cm.load_app_settings() or {}
            return int(((app_settings.get('backup') or {}).get('max_parallel_jobs')) or 3)
        except Exception:
            return 3

    def perform_pitr_restore(self, target_time_iso: str) -> None:
        """시점 복구(PITR) 실행(스켈레톤)
        - target_time_iso: ISO 포맷 문자열 (예: '2025-01-01T00:00:00Z')
        - 실제 복구는 별도 환경에서 베이스 백업 복원 후 WAL 적용(recovery) 절차가 필요
        """
        self.logger.warning("PITR 스켈레톤 - target_time=%s: 실제 복구는 운영 가이드를 따르십시오.", target_time_iso)

    def _sha256(self, file_path: Path) -> str:
        """파일의 SHA-256 체크섬 계산"""
        h = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b''):
                h.update(chunk)
        return h.hexdigest()

    def _build_pg_dump_cmd(self, db: Database, dump_file: Path, fmt: str = 'plain') -> list[str]:
        """pg_dump 명령어 구성
        - fmt: 'plain' (SQL) 기준으로 구성
        """
        return [
            'pg_dump',
            '-h', str(db.host),
            '-p', str(db.port),
            '-U', str(db.username),
            '-d', str(db.database_name),
            '-F', 'p' if fmt == 'plain' else 'c',
            '-f', str(dump_file),
        ]

    def _run_pg_dump(self, db: Database, dump_file: Path, password: Optional[str]) -> None:
        """pg_dump 실행
        - 비밀번호는 환경변수 PGPASSWORD 로 전달
        """
        env = os.environ.copy()
        if password:
            env['PGPASSWORD'] = password
        cmd = self._build_pg_dump_cmd(db, dump_file, fmt='plain')
        # Windows 환경에서도 동작하도록 shell=False 고정
        completed = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if completed.returncode != 0:
            raise RuntimeError(f"pg_dump 실패: {completed.stderr}")

    def _gzip_compress(self, src: Path, dst: Path) -> None:
        """gzip 압축 수행 (표준 라이브러리 사용)"""
        import gzip
        with open(src, 'rb') as f_in:
            with gzip.open(dst, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)

    def _aes_gcm_encrypt_file(self, src: Path, dst: Path, key_str: str) -> None:
        """AES-256-GCM 파일 암호화
        - key_str: 32자 ENCRYPTION_KEY (바이트 길이 32 가정)
        - nonce(IV)는 12바이트 랜덤 생성
        - 출력 파일 구성: [nonce(12)][ciphertext+tag]
        """
        if not key_str or len(key_str) != 32:
            raise ValueError("ENCRYPTION_KEY는 32자여야 합니다.")
        key = key_str.encode('utf-8')
        aesgcm = AESGCM(key)
        nonce = secrets.token_bytes(12)
        plaintext = src.read_bytes()
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        with open(dst, 'wb') as f:
            f.write(nonce + ciphertext)

    def _aes_gcm_encrypt_file_v2(self, src: Path, dst: Path, key_id: str, key_str: str) -> None:
        """AES-256-GCM 파일 암호화(V2 포맷)
        - 포맷: [MAGIC(4='LBM1')][key_id_len(1)][key_id][nonce(12)][ciphertext+tag]
        - key_id는 settings.yaml의 security.encryption.active_key_id
        """
        if not key_str or len(key_str) != 32:
            raise ValueError("ENCRYPTION_KEY는 32자여야 합니다.")
        if not key_id:
            raise ValueError("key_id가 비어 있습니다.")
        key = key_str.encode('utf-8')
        aesgcm = AESGCM(key)
        nonce = secrets.token_bytes(12)
        plaintext = src.read_bytes()
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        key_id_bytes = key_id.encode('utf-8')
        if len(key_id_bytes) > 255:
            raise ValueError("key_id 길이는 255바이트 이하여야 합니다.")
        with open(dst, 'wb') as f:
            f.write(MAGIC_V1)
            f.write(bytes([len(key_id_bytes)]))
            f.write(key_id_bytes)
            f.write(nonce)
            f.write(ciphertext)

    def _aes_gcm_decrypt_file_v2(self, src: Path, dst: Path, key_lookup: dict[str, str]) -> None:
        """AES-256-GCM 파일 복호화(V2 포맷)
        - key_lookup: {key_id: key_str(32자)} 딕셔너리
        - 입력 포맷이 V1이 아닐 경우, 구버전 포맷([nonce][ciphertext])로 간주하고 key_lookup의 active 키를 사용 시도
        """
        data = src.read_bytes()
        offset = 0
        try:
            if data[:4] == MAGIC_V1:
                offset = 4
                key_id_len = data[offset]
                offset += 1
                key_id = data[offset:offset+key_id_len].decode('utf-8')
                offset += key_id_len
                nonce = data[offset:offset+12]
                offset += 12
                ciphertext = data[offset:]
                key_str = key_lookup.get(key_id)
                if not key_str or len(key_str) != 32:
                    raise ValueError("해당 key_id에 대한 올바른 키가 없습니다.")
                key = key_str.encode('utf-8')
                aesgcm = AESGCM(key)
                plaintext = aesgcm.decrypt(nonce, ciphertext, None)
                dst.write_bytes(plaintext)
                return
        except Exception as e:
            # 매직 포맷 실패 시 구버전 처리 시도
            pass
        # 구버전 포맷: [nonce(12)][ciphertext]
        if len(data) < 13:
            raise ValueError("암호문 형식이 올바르지 않습니다.")
        nonce = data[:12]
        ciphertext = data[12:]
        # key_lookup의 첫 번째 키를 사용(호환 목적)
        for key_str in key_lookup.values():
            if key_str and len(key_str) == 32:
                try:
                    aesgcm = AESGCM(key_str.encode('utf-8'))
                    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
                    dst.write_bytes(plaintext)
                    return
                except Exception:
                    continue
        raise ValueError("유효한 복호화 키를 찾을 수 없습니다.")

    def _pg_dump_version(self) -> Optional[str]:
        """pg_dump 버전 문자열 조회 (없으면 None)"""
        try:
            c = subprocess.run(['pg_dump', '--version'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            if c.returncode == 0:
                return c.stdout.strip()
        except Exception:
            return None
        return None

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
