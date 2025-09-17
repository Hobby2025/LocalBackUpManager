"""
보안 감사 로깅 시스템
- 인증, 권한 변경, 키 사용 등 보안 이벤트 추적
- 구조화된 로그 포맷으로 감사 추적성 확보
- 민감한 정보 마스킹 처리

주의:
- 변수명 변경 금지
- 외부 의존성 추가 없이 기존 패키지만 사용
- CRLF 라인 시퀀스 유지
- 한글 주석
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import os

from app.config import settings


class SecurityAuditLogger:
    """보안 감사 로거"""
    
    def __init__(self):
        # 보안 감사 전용 로거 설정
        self.audit_logger = logging.getLogger('security_audit')
        self.audit_logger.setLevel(logging.INFO)
        
        # 감사 로그 파일 경로
        audit_log_path = Path("data/logs/security_audit.log")
        audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 파일 핸들러 설정 (기존 핸들러 중복 방지)
        if not self.audit_logger.handlers:
            handler = logging.FileHandler(audit_log_path, encoding='utf-8')
            formatter = logging.Formatter(
                '%(asctime)s - SECURITY_AUDIT - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.audit_logger.addHandler(handler)
    
    def _mask_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """민감한 데이터 마스킹 처리"""
        masked = data.copy()
        sensitive_keys = ['password', 'key', 'token', 'secret', 'credential']
        
        for key, value in masked.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                if isinstance(value, str) and len(value) > 4:
                    masked[key] = value[:2] + '*' * (len(value) - 4) + value[-2:]
                else:
                    masked[key] = '***'
        
        return masked
    
    def log_authentication_event(self, event_type: str, username: str, 
                                ip_address: Optional[str] = None, 
                                user_agent: Optional[str] = None,
                                success: bool = True, 
                                failure_reason: Optional[str] = None):
        """인증 이벤트 로깅"""
        event_data = {
            'event_type': 'AUTHENTICATION',
            'sub_type': event_type,  # LOGIN, LOGOUT, LOGIN_FAILED
            'username': username,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'success': success,
            'failure_reason': failure_reason,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # 민감한 데이터 마스킹
        masked_data = self._mask_sensitive_data(event_data)
        
        log_message = f"인증 이벤트: {json.dumps(masked_data, ensure_ascii=False)}"
        
        if success:
            self.audit_logger.info(log_message)
        else:
            self.audit_logger.warning(log_message)
    
    def log_authorization_event(self, event_type: str, username: str, 
                              resource: str, action: str, 
                              success: bool = True,
                              required_role: Optional[str] = None,
                              user_role: Optional[str] = None):
        """권한 검사 이벤트 로깅"""
        event_data = {
            'event_type': 'AUTHORIZATION',
            'sub_type': event_type,  # ACCESS_GRANTED, ACCESS_DENIED
            'username': username,
            'resource': resource,
            'action': action,
            'success': success,
            'required_role': required_role,
            'user_role': user_role,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        log_message = f"권한 이벤트: {json.dumps(event_data, ensure_ascii=False)}"
        
        if success:
            self.audit_logger.info(log_message)
        else:
            self.audit_logger.warning(log_message)
    
    def log_encryption_event(self, event_type: str, key_id: str,
                           file_path: Optional[str] = None,
                           operation: Optional[str] = None,
                           success: bool = True,
                           error_message: Optional[str] = None):
        """암호화 키 사용 이벤트 로깅"""
        event_data = {
            'event_type': 'ENCRYPTION',
            'sub_type': event_type,  # KEY_USED, KEY_ROTATED, ENCRYPT, DECRYPT
            'key_id': key_id,
            'file_path': file_path,
            'operation': operation,
            'success': success,
            'error_message': error_message,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        log_message = f"암호화 이벤트: {json.dumps(event_data, ensure_ascii=False)}"
        
        if success:
            self.audit_logger.info(log_message)
        else:
            self.audit_logger.error(log_message)
    
    def log_configuration_event(self, event_type: str, username: str,
                              config_section: str, 
                              changes: Dict[str, Any],
                              success: bool = True):
        """설정 변경 이벤트 로깅"""
        event_data = {
            'event_type': 'CONFIGURATION',
            'sub_type': event_type,  # CONFIG_CHANGED, CONFIG_VIEWED
            'username': username,
            'config_section': config_section,
            'changes': self._mask_sensitive_data(changes),
            'success': success,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        log_message = f"설정 이벤트: {json.dumps(event_data, ensure_ascii=False)}"
        self.audit_logger.info(log_message)
    
    def log_data_access_event(self, event_type: str, username: str,
                            resource_type: str, resource_id: str,
                            action: str, success: bool = True):
        """데이터 접근 이벤트 로깅"""
        event_data = {
            'event_type': 'DATA_ACCESS',
            'sub_type': event_type,  # BACKUP_CREATED, BACKUP_DELETED, DATABASE_ADDED, DATABASE_DELETED
            'username': username,
            'resource_type': resource_type,  # backup, database, schedule
            'resource_id': resource_id,
            'action': action,  # CREATE, READ, UPDATE, DELETE
            'success': success,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        log_message = f"데이터 접근 이벤트: {json.dumps(event_data, ensure_ascii=False)}"
        self.audit_logger.info(log_message)
    
    def log_system_event(self, event_type: str, details: Dict[str, Any]):
        """시스템 이벤트 로깅"""
        event_data = {
            'event_type': 'SYSTEM',
            'sub_type': event_type,  # STARTUP, SHUTDOWN, ERROR
            'details': details,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        log_message = f"시스템 이벤트: {json.dumps(event_data, ensure_ascii=False)}"
        self.audit_logger.info(log_message)


# 전역 감사 로거 인스턴스
_audit_logger = None

def get_security_audit_logger() -> SecurityAuditLogger:
    """보안 감사 로거 인스턴스 반환 (싱글톤)"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = SecurityAuditLogger()
    return _audit_logger


# 편의 함수들
def audit_login(username: str, ip_address: str = None, user_agent: str = None, success: bool = True, failure_reason: str = None):
    """로그인 감사 로깅"""
    logger = get_security_audit_logger()
    event_type = 'LOGIN' if success else 'LOGIN_FAILED'
    logger.log_authentication_event(event_type, username, ip_address, user_agent, success, failure_reason)

def audit_logout(username: str, ip_address: str = None):
    """로그아웃 감사 로깅"""
    logger = get_security_audit_logger()
    logger.log_authentication_event('LOGOUT', username, ip_address)

def audit_access_denied(username: str, resource: str, action: str, required_role: str = None, user_role: str = None):
    """접근 거부 감사 로깅"""
    logger = get_security_audit_logger()
    logger.log_authorization_event('ACCESS_DENIED', username, resource, action, False, required_role, user_role)

def audit_access_granted(username: str, resource: str, action: str, user_role: str = None):
    """접근 허용 감사 로깅"""
    logger = get_security_audit_logger()
    logger.log_authorization_event('ACCESS_GRANTED', username, resource, action, True, user_role=user_role)

def audit_encryption_key_used(key_id: str, operation: str, file_path: str = None, success: bool = True):
    """암호화 키 사용 감사 로깅"""
    logger = get_security_audit_logger()
    logger.log_encryption_event('KEY_USED', key_id, file_path, operation, success)

def audit_config_change(username: str, section: str, changes: Dict[str, Any]):
    """설정 변경 감사 로깅"""
    logger = get_security_audit_logger()
    logger.log_configuration_event('CONFIG_CHANGED', username, section, changes)
