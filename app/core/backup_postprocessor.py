"""
백업 후처리 공통 모듈
- 압축 (gzip, lz4, zstd)
- 암호화 (AES-256-GCM)
- 체크섬 계산 (SHA-256)
- 메타데이터 생성

주의:
- 변수명은 기존 코드와 충돌하지 않도록 새로운 범위에서만 정의
- 외부 의존성 추가 금지 (requirements.txt 내 패키지만 사용)
- Windows/Unix 환경 모두 동작
"""

from __future__ import annotations

import gzip
import hashlib
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple, Any

from app.config import get_config_manager

# 암호화에 필요한 모듈 (requirements.txt의 cryptography 사용)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import secrets

# 암호화 포맷 매직 헤더
# 포맷: [MAGIC(4='LBM1')][key_id_len(1)][key_id][nonce(12)][ciphertext+tag]
MAGIC_V1 = b"LBM1"


class BackupPostProcessor:
    """백업 후처리 공통 클래스"""
    
    def __init__(self) -> None:
        pass
    
    # ========================================
    # 압축 관련 메서드
    # ========================================
    
    def get_available_compression_tools(self) -> Dict[str, bool]:
        """사용 가능한 압축 도구 확인"""
        tools = {
            "gzip": True,  # 파이썬 내장
            "lz4": False,
            "zstd": False,
        }
        
        # 외부 도구 확인
        for tool in ["lz4", "zstd"]:
            try:
                result = subprocess.run([tool, "--version"], 
                                      capture_output=True, timeout=5)
                tools[tool] = result.returncode == 0
            except (subprocess.TimeoutExpired, FileNotFoundError):
                tools[tool] = False
        
        return tools
    
    def compress_file(
        self, 
        input_path: Path, 
        output_path: Path, 
        compression_type: str = "gzip",
        compression_level: int = 6
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """파일 압축
        
        Args:
            input_path: 입력 파일 경로
            output_path: 출력 파일 경로
            compression_type: 압축 타입 (gzip, lz4, zstd)
            compression_level: 압축 레벨 (1-9)
        
        Returns:
            Tuple[bool, str, Dict[str, Any]]: (성공여부, 오류메시지, 메타데이터)
        """
        try:
            start_time = datetime.utcnow()
            original_size = input_path.stat().st_size
            
            if compression_type == "gzip":
                success, error, metadata = self._compress_gzip(
                    input_path, output_path, compression_level
                )
            elif compression_type == "lz4":
                success, error, metadata = self._compress_lz4(
                    input_path, output_path, compression_level
                )
            elif compression_type == "zstd":
                success, error, metadata = self._compress_zstd(
                    input_path, output_path, compression_level
                )
            else:
                return False, f"지원하지 않는 압축 타입: {compression_type}", {}
            
            if success:
                end_time = datetime.utcnow()
                compressed_size = output_path.stat().st_size if output_path.exists() else 0
                compression_ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
                
                metadata.update({
                    "compression_type": compression_type,
                    "compression_level": compression_level,
                    "original_size_bytes": original_size,
                    "compressed_size_bytes": compressed_size,
                    "compression_ratio_percent": round(compression_ratio, 2),
                    "compression_duration_seconds": int((end_time - start_time).total_seconds()),
                })
            
            return success, error, metadata
            
        except Exception as e:
            return False, f"압축 오류: {str(e)}", {}
    
    def _compress_gzip(self, input_path: Path, output_path: Path, level: int) -> Tuple[bool, str, Dict[str, Any]]:
        """gzip 압축"""
        try:
            with open(input_path, 'rb') as f_in:
                with gzip.open(output_path, 'wb', compresslevel=level) as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            return True, "", {"compression_tool": "gzip"}
            
        except Exception as e:
            return False, f"gzip 압축 오류: {str(e)}", {"compression_tool": "gzip"}
    
    def _compress_lz4(self, input_path: Path, output_path: Path, level: int) -> Tuple[bool, str, Dict[str, Any]]:
        """lz4 압축"""
        try:
            cmd = ["lz4", f"-{level}", str(input_path), str(output_path)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            
            if result.returncode == 0:
                return True, "", {"compression_tool": "lz4", "stdout": result.stdout}
            else:
                return False, f"lz4 압축 실패: {result.stderr}", {"compression_tool": "lz4"}
                
        except subprocess.TimeoutExpired:
            return False, "lz4 압축 시간 초과", {"compression_tool": "lz4"}
        except Exception as e:
            return False, f"lz4 압축 오류: {str(e)}", {"compression_tool": "lz4"}
    
    def _compress_zstd(self, input_path: Path, output_path: Path, level: int) -> Tuple[bool, str, Dict[str, Any]]:
        """zstd 압축"""
        try:
            cmd = ["zstd", f"-{level}", str(input_path), "-o", str(output_path)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            
            if result.returncode == 0:
                return True, "", {"compression_tool": "zstd", "stdout": result.stdout}
            else:
                return False, f"zstd 압축 실패: {result.stderr}", {"compression_tool": "zstd"}
                
        except subprocess.TimeoutExpired:
            return False, "zstd 압축 시간 초과", {"compression_tool": "zstd"}
        except Exception as e:
            return False, f"zstd 압축 오류: {str(e)}", {"compression_tool": "zstd"}
    
    # ========================================
    # 암호화 관련 메서드
    # ========================================
    
    def _get_active_encryption_key_info(self) -> Optional[Tuple[str, str]]:
        """활성 키의 (key_id, key_str) 튜플 반환. 없으면 None"""
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
    
    def encrypt_file(
        self, 
        input_path: Path, 
        output_path: Path
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """파일 암호화 (AES-256-GCM)
        
        Args:
            input_path: 입력 파일 경로
            output_path: 출력 파일 경로
        
        Returns:
            Tuple[bool, str, Dict[str, Any]]: (성공여부, 오류메시지, 메타데이터)
        """
        try:
            start_time = datetime.utcnow()
            
            # 암호화 키 정보 가져오기
            key_info = self._get_active_encryption_key_info()
            if not key_info:
                return False, "암호화 키를 찾을 수 없습니다.", {}
            
            key_id, key_str = key_info
            key_bytes = key_str.encode('utf-8')
            
            # AESGCM 인스턴스 생성
            aesgcm = AESGCM(key_bytes)
            nonce = secrets.token_bytes(12)  # 96비트 nonce
            
            # 파일 읽기 및 암호화
            with open(input_path, 'rb') as f_in:
                plaintext = f_in.read()
            
            ciphertext = aesgcm.encrypt(nonce, plaintext, None)
            
            # 암호화된 파일 저장 (포맷: MAGIC + key_id_len + key_id + nonce + ciphertext)
            with open(output_path, 'wb') as f_out:
                f_out.write(MAGIC_V1)  # 매직 헤더
                key_id_bytes = key_id.encode('utf-8')
                f_out.write(bytes([len(key_id_bytes)]))  # key_id 길이
                f_out.write(key_id_bytes)  # key_id
                f_out.write(nonce)  # nonce
                f_out.write(ciphertext)  # 암호화된 데이터
            
            end_time = datetime.utcnow()
            original_size = input_path.stat().st_size
            encrypted_size = output_path.stat().st_size
            
            metadata = {
                "encryption_algorithm": "AES-256-GCM",
                "key_id": key_id,
                "original_size_bytes": original_size,
                "encrypted_size_bytes": encrypted_size,
                "encryption_duration_seconds": int((end_time - start_time).total_seconds()),
            }
            
            return True, "", metadata
            
        except Exception as e:
            return False, f"암호화 오류: {str(e)}", {}
    
    # ========================================
    # 체크섬 관련 메서드
    # ========================================
    
    def calculate_checksum(
        self, 
        file_path: Path, 
        algorithm: str = "sha256"
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """파일 체크섬 계산
        
        Args:
            file_path: 파일 경로
            algorithm: 해시 알고리즘 (sha256, md5, sha1)
        
        Returns:
            Tuple[bool, str, Dict[str, Any]]: (성공여부, 체크섬, 메타데이터)
        """
        try:
            start_time = datetime.utcnow()
            
            # 해시 객체 생성
            if algorithm == "sha256":
                hash_obj = hashlib.sha256()
            elif algorithm == "md5":
                hash_obj = hashlib.md5()
            elif algorithm == "sha1":
                hash_obj = hashlib.sha1()
            else:
                return False, f"지원하지 않는 해시 알고리즘: {algorithm}", {}
            
            # 파일을 청크 단위로 읽어서 해시 계산
            with open(file_path, 'rb') as f:
                while chunk := f.read(8192):  # 8KB 청크
                    hash_obj.update(chunk)
            
            checksum = hash_obj.hexdigest()
            end_time = datetime.utcnow()
            
            metadata = {
                "checksum_algorithm": algorithm,
                "file_size_bytes": file_path.stat().st_size,
                "checksum_duration_seconds": int((end_time - start_time).total_seconds()),
            }
            
            return True, checksum, metadata
            
        except Exception as e:
            return False, f"체크섬 계산 오류: {str(e)}", {}
    
    # ========================================
    # 통합 후처리 메서드
    # ========================================
    
    def process_backup_file(
        self,
        input_path: Path,
        output_dir: Path,
        *,
        compress: bool = True,
        compression_type: str = "gzip",
        compression_level: int = 6,
        encrypt: bool = True,
        calculate_checksum: bool = True,
        checksum_algorithm: str = "sha256",
        cleanup_intermediate: bool = True,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """백업 파일 통합 후처리
        
        Args:
            input_path: 입력 백업 파일
            output_dir: 출력 디렉터리
            compress: 압축 여부
            compression_type: 압축 타입
            compression_level: 압축 레벨
            encrypt: 암호화 여부
            calculate_checksum: 체크섬 계산 여부
            checksum_algorithm: 체크섬 알고리즘
            cleanup_intermediate: 중간 파일 정리 여부
        
        Returns:
            Tuple[bool, str, Dict[str, Any]]: (성공여부, 최종파일경로, 메타데이터)
        """
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            current_file = input_path
            intermediate_files = []
            metadata = {}
            
            # 1. 압축 처리
            if compress:
                compressed_file = output_dir / f"{input_path.stem}.{compression_type}"
                success, error, compress_meta = self.compress_file(
                    current_file, compressed_file, compression_type, compression_level
                )
                if not success:
                    return False, error, compress_meta
                
                if current_file != input_path:
                    intermediate_files.append(current_file)
                current_file = compressed_file
                metadata.update(compress_meta)
            
            # 2. 암호화 처리
            if encrypt:
                encrypted_file = output_dir / f"{current_file.name}.enc"
                success, error, encrypt_meta = self.encrypt_file(current_file, encrypted_file)
                if not success:
                    return False, error, encrypt_meta
                
                if current_file != input_path:
                    intermediate_files.append(current_file)
                current_file = encrypted_file
                metadata.update(encrypt_meta)
            
            # 3. 체크섬 계산
            if calculate_checksum:
                success, checksum, checksum_meta = self.calculate_checksum(
                    current_file, checksum_algorithm
                )
                if not success:
                    return False, checksum, checksum_meta
                
                metadata.update(checksum_meta)
                metadata["checksum"] = checksum
                
                # 체크섬 파일 저장
                checksum_file = output_dir / f"{current_file.name}.{checksum_algorithm}"
                with open(checksum_file, 'w') as f:
                    f.write(f"{checksum}  {current_file.name}\n")
            
            # 4. 중간 파일 정리
            if cleanup_intermediate:
                for temp_file in intermediate_files:
                    try:
                        if temp_file.exists():
                            temp_file.unlink()
                    except Exception:
                        pass  # 정리 실패는 무시
            
            # 5. 최종 메타데이터 업데이트
            metadata.update({
                "final_file_path": str(current_file),
                "final_file_size_bytes": current_file.stat().st_size,
                "processing_steps": {
                    "compressed": compress,
                    "encrypted": encrypt,
                    "checksum_calculated": calculate_checksum,
                },
            })
            
            return True, str(current_file), metadata
            
        except Exception as e:
            # 오류 발생 시 중간 파일들 정리
            for temp_file in intermediate_files:
                try:
                    if temp_file.exists():
                        temp_file.unlink()
                except Exception:
                    pass
            
            return False, f"후처리 오류: {str(e)}", {}


# 전역 인스턴스
backup_postprocessor = BackupPostProcessor()
