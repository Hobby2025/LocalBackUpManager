"""
pg_dump 기반 기본 백업 엔진
- 데이터베이스 덤프 실행
- 압축(gzip) 지원
- 체크섬(SHA-256) 계산 및 메타데이터 갱신

주의:
- 변수명은 변경하지 않음
- 외부 의존성 추가 없이 표준 라이브러리/기존 패키지만 사용
- Windows/Unix 모두 동작하도록 경로 처리
"""

import os
import subprocess
import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.config import settings
from app.database import (
    SessionLocal,
    Database,
    Backup,
)

# 암호화에 필요한 모듈 (requirements.txt의 cryptography 사용)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import secrets


class BackupEngine:
    """기본 백업 엔진 클래스"""

    def __init__(self):
        # 백업/로그/임시 디렉터리 보장 생성
        Path(settings.BACKUP_BASE_PATH).mkdir(parents=True, exist_ok=True)
        Path(settings.TEMP_PATH).mkdir(parents=True, exist_ok=True)

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
        """백업 실행 메인 함수
        - 새로운 DB 세션을 생성하여 메타데이터 갱신
        - 상태: pending -> running -> completed/failed
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

            # 출력 파일 경로/이름 생성: backups/<db_name>/<timestamp>_<backup_id>.sql(.gz)
            ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            db_dir = Path(settings.BACKUP_BASE_PATH) / target_db.database_name
            db_dir.mkdir(parents=True, exist_ok=True)
            sql_path = db_dir / f"{ts}_{backup_id}.sql"

            # TODO: password_encrypted 복호화 로직 적용 (현재는 평문으로 가정)
            password = target_db.password_encrypted

            # 덤프 실행
            self._run_pg_dump(target_db, sql_path, password)

            # 압축 설정이 gzip 인 경우 gzip 처리
            compressed_path: Optional[Path] = None
            if settings.DEFAULT_COMPRESSION.lower() == 'gzip':
                compressed_path = Path(str(sql_path) + '.gz')
                self._gzip_compress(sql_path, compressed_path)
                # 원본 SQL은 공간 절약을 위해 삭제 (원하면 보존 가능)
                try:
                    sql_path.unlink(missing_ok=True)
                except TypeError:
                    # Python 3.7 호환 (missing_ok 미지원) - 존재 시 삭제
                    if sql_path.exists():
                        sql_path.unlink()

            # 파일 메타데이터 계산
            final_path = compressed_path or sql_path

            # 암호화 설정이 활성화된 경우 AES-256-GCM으로 암호화 (.enc)
            encrypted = False
            if settings.DEFAULT_ENCRYPTION:
                enc_path = Path(str(final_path) + '.enc')
                self._aes_gcm_encrypt_file(final_path, enc_path, settings.ENCRYPTION_KEY)
                # 평문 파일 삭제
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

            # 추가 메타데이터: 압축 크기/압축비, pg_dump 버전
            if compressed_path:
                try:
                    # 압축 전 크기: 압축 파일명에서 .gz 제거한 원래 sql 파일 크기 (이미 삭제되었을 수 있으므로 예외 처리)
                    # 삭제 이전의 크기를 알 수 없으면 압축비 계산은 생략
                    pass
                except Exception:
                    pass
                # 최소한 compressed_size는 기록
                backup.compressed_size = file_size
            # pg_dump 버전 기록
            ver = self._pg_dump_version()
            if ver:
                backup.pg_dump_version = ver
            db_session.commit()

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
        finally:
            db_session.close()
