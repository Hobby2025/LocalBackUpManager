"""
암호화 키 순환 유틸리티
- 기존 백업 파일 재암호화
- 키 전환 및 무중단 서비스 지원
- 배치 처리 및 진행률 추적

주의:
- 변수명 변경 금지
- 외부 의존성 추가 없이 기존 패키지만 사용
- CRLF 라인 시퀀스 유지
- 한글 주석
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import shutil

from app.config import get_config_manager
from app.database import SessionLocal, Backup
from app.core.backup_engine import BackupEngine

logger = logging.getLogger(__name__)


class KeyRotationManager:
    """암호화 키 순환 관리자"""
    
    def __init__(self):
        self.backup_engine = BackupEngine()
        self.logger = logging.getLogger(__name__)
    
    def get_all_encryption_keys(self) -> Dict[str, str]:
        """설정에서 모든 암호화 키 조회
        반환: {key_id: key_str} 딕셔너리
        """
        try:
            cm = get_config_manager()
            app_settings = cm.load_app_settings() or {}
            sec = (app_settings.get('security') or {})
            enc = (sec.get('encryption') or {})
            keys = enc.get('keys') or []
            
            result = {}
            for item in keys:
                try:
                    key_id = (item or {}).get('id')
                    key_str = (item or {}).get('key')
                    if key_id and isinstance(key_str, str) and len(key_str) == 32:
                        result[key_id] = key_str
                except Exception:
                    continue
            return result
        except Exception as e:
            self.logger.error(f"암호화 키 조회 실패: {e}")
            return {}
    
    def get_encrypted_backup_files(self) -> List[Tuple[str, Path]]:
        """암호화된 백업 파일 목록 조회
        반환: [(backup_id, file_path), ...] 리스트
        """
        db_session = SessionLocal()
        try:
            backups = db_session.query(Backup).filter(
                Backup.is_encrypted == True,
                Backup.file_path.isnot(None),
                Backup.status == 'completed'
            ).all()
            
            result = []
            for backup in backups:
                file_path = Path(backup.file_path)
                if file_path.exists():
                    result.append((backup.id, file_path))
            return result
        finally:
            db_session.close()
    
    def rotate_backup_file(self, backup_id: str, file_path: Path, 
                          old_keys: Dict[str, str], new_key_id: str, new_key_str: str) -> bool:
        """단일 백업 파일 키 순환
        - 기존 키로 복호화 후 새 키로 재암호화
        """
        try:
            # 임시 파일 경로
            temp_decrypted = file_path.with_suffix('.tmp_decrypted')
            temp_encrypted = file_path.with_suffix('.tmp_encrypted')
            
            # 1. 복호화
            self.backup_engine._aes_gcm_decrypt_file_v2(file_path, temp_decrypted, old_keys)
            
            # 2. 새 키로 재암호화
            self.backup_engine._aes_gcm_encrypt_file_v2(temp_decrypted, temp_encrypted, new_key_id, new_key_str)
            
            # 3. 원본 파일 백업 및 교체
            backup_path = file_path.with_suffix(file_path.suffix + '.backup')
            shutil.move(str(file_path), str(backup_path))
            shutil.move(str(temp_encrypted), str(file_path))
            
            # 4. 임시 파일 정리
            try:
                temp_decrypted.unlink(missing_ok=True)
                # 성공 시 백업 파일도 정리
                backup_path.unlink(missing_ok=True)
            except Exception:
                pass
            
            self.logger.info(f"키 순환 완료: backup_id={backup_id}, file={file_path.name}")
            return True
            
        except Exception as e:
            # 실패 시 임시 파일 정리
            try:
                temp_decrypted.unlink(missing_ok=True)
                temp_encrypted.unlink(missing_ok=True)
            except Exception:
                pass
            
            self.logger.error(f"키 순환 실패: backup_id={backup_id}, error={e}")
            return False
    
    def rotate_all_backups(self, new_key_id: str) -> Dict[str, any]:
        """모든 암호화된 백업 파일의 키 순환 실행
        반환: 진행 결과 딕셔너리
        """
        result = {
            'started_at': datetime.utcnow().isoformat(),
            'total_files': 0,
            'success_count': 0,
            'failed_count': 0,
            'failed_files': [],
            'completed_at': None
        }
        
        try:
            # 키 정보 조회
            all_keys = self.get_all_encryption_keys()
            if new_key_id not in all_keys:
                raise ValueError(f"새 키 ID '{new_key_id}'를 찾을 수 없습니다.")
            
            new_key_str = all_keys[new_key_id]
            
            # 암호화된 백업 파일 목록
            encrypted_files = self.get_encrypted_backup_files()
            result['total_files'] = len(encrypted_files)
            
            self.logger.info(f"키 순환 시작: {result['total_files']}개 파일, 새 키 ID={new_key_id}")
            
            # 각 파일 처리
            for backup_id, file_path in encrypted_files:
                success = self.rotate_backup_file(backup_id, file_path, all_keys, new_key_id, new_key_str)
                if success:
                    result['success_count'] += 1
                else:
                    result['failed_count'] += 1
                    result['failed_files'].append({
                        'backup_id': backup_id,
                        'file_path': str(file_path)
                    })
            
            result['completed_at'] = datetime.utcnow().isoformat()
            self.logger.info(f"키 순환 완료: 성공={result['success_count']}, 실패={result['failed_count']}")
            
        except Exception as e:
            result['error'] = str(e)
            result['completed_at'] = datetime.utcnow().isoformat()
            self.logger.error(f"키 순환 중 오류: {e}")
        
        return result
    
    def validate_key_rotation_readiness(self, new_key_id: str) -> Dict[str, any]:
        """키 순환 준비 상태 검증
        - 새 키 존재 여부
        - 기존 키들 유효성
        - 디스크 공간 충분성
        """
        result = {
            'ready': False,
            'checks': {},
            'warnings': []
        }
        
        try:
            # 1. 키 존재 검증
            all_keys = self.get_all_encryption_keys()
            result['checks']['new_key_exists'] = new_key_id in all_keys
            result['checks']['old_keys_count'] = len(all_keys)
            
            # 2. 암호화 파일 목록
            encrypted_files = self.get_encrypted_backup_files()
            result['checks']['encrypted_files_count'] = len(encrypted_files)
            
            # 3. 디스크 공간 검사 (대략적)
            if encrypted_files:
                total_size = sum(f[1].stat().st_size for f in encrypted_files if f[1].exists())
                # 임시 파일용 여유 공간 필요 (원본 크기의 2배)
                required_space = total_size * 2
                
                # 백업 디렉터리의 여유 공간 확인
                backup_dir = Path(encrypted_files[0][1]).parent
                free_space = shutil.disk_usage(backup_dir).free
                
                result['checks']['total_backup_size'] = total_size
                result['checks']['required_space'] = required_space
                result['checks']['available_space'] = free_space
                result['checks']['space_sufficient'] = free_space >= required_space
                
                if not result['checks']['space_sufficient']:
                    result['warnings'].append(f"디스크 공간 부족: 필요={required_space//1024//1024}MB, 여유={free_space//1024//1024}MB")
            
            # 전체 준비 상태 판정
            result['ready'] = (
                result['checks'].get('new_key_exists', False) and
                result['checks'].get('old_keys_count', 0) > 0 and
                result['checks'].get('space_sufficient', True)
            )
            
        except Exception as e:
            result['error'] = str(e)
            self.logger.error(f"키 순환 준비 검증 실패: {e}")
        
        return result


def get_key_rotation_manager() -> KeyRotationManager:
    """키 순환 관리자 인스턴스 반환"""
    return KeyRotationManager()
