"""
감사 로깅 미들웨어
모든 API 요청/응답을 자동으로 감사 로그에 기록
"""

import time
import json
import uuid
from typing import Callable, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.audit_service import audit_service


class AuditMiddleware(BaseHTTPMiddleware):
    """감사 로깅 미들웨어"""
    
    def __init__(self, app, exclude_paths: Optional[list] = None):
        super().__init__(app)
        # 감사 로깅에서 제외할 경로들
        self.exclude_paths = exclude_paths or [
            '/docs',
            '/redoc',
            '/openapi.json',
            '/favicon.ico',
            '/static',
            '/health',
            '/metrics'
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> StarletteResponse:
        """요청 처리 및 감사 로깅"""
        
        # 제외 경로 확인
        if self._should_exclude_path(request.url.path):
            return await call_next(request)
        
        # 요청 시작 시간 기록
        start_time = time.time()
        
        # 요청 ID 생성
        request_id = str(uuid.uuid4())
        
        # 요청 정보 추출
        user_info = self._extract_user_info(request)
        
        # 요청 본문 크기 계산
        request_body_size = self._get_request_body_size(request)
        
        try:
            # 다음 미들웨어/핸들러 호출
            response = await call_next(request)
            
            # 응답 시간 계산
            process_time = time.time() - start_time
            response_time_ms = int(process_time * 1000)
            
            # 응답 크기 계산
            response_size = self._get_response_size(response)
            
            # 데이터베이스 세션 생성하여 접근 로그 기록
            db = next(get_db())
            try:
                audit_service.log_access(
                    db=db,
                    request=request,
                    response_status=response.status_code,
                    response_size=response_size,
                    response_time_ms=response_time_ms,
                    user_id=user_info.get('user_id'),
                    username=user_info.get('username'),
                    is_authenticated=user_info.get('is_authenticated', False),
                    auth_method=user_info.get('auth_method')
                )
                
                # 실패한 인증 시도 감지
                if response.status_code == 401:
                    self._handle_authentication_failure(db, request, user_info)
                
                # 권한 없음 감지
                elif response.status_code == 403:
                    self._handle_authorization_failure(db, request, user_info)
                
                # 서버 오류 감지
                elif response.status_code >= 500:
                    self._handle_server_error(db, request, user_info, response.status_code)
                
            finally:
                db.close()
            
            # 응답에 요청 ID 헤더 추가
            response.headers['X-Request-ID'] = request_id
            
            return response
            
        except Exception as e:
            # 예외 발생 시 처리
            process_time = time.time() - start_time
            response_time_ms = int(process_time * 1000)
            
            # 오류 로그 기록
            db = next(get_db())
            try:
                audit_service.log_access(
                    db=db,
                    request=request,
                    response_status=500,
                    response_size=0,
                    response_time_ms=response_time_ms,
                    user_id=user_info.get('user_id'),
                    username=user_info.get('username'),
                    is_authenticated=user_info.get('is_authenticated', False),
                    auth_method=user_info.get('auth_method')
                )
                
                # 서버 오류 보안 이벤트 기록
                self._handle_server_error(db, request, user_info, 500, str(e))
                
            finally:
                db.close()
            
            # 예외 재발생
            raise e
    
    def _should_exclude_path(self, path: str) -> bool:
        """경로가 감사 로깅에서 제외되어야 하는지 확인"""
        return any(path.startswith(exclude_path) for exclude_path in self.exclude_paths)
    
    def _extract_user_info(self, request: Request) -> dict:
        """요청에서 사용자 정보 추출"""
        user_info = {
            'user_id': None,
            'username': None,
            'is_authenticated': False,
            'auth_method': None
        }
        
        # Authorization 헤더 확인
        auth_header = request.headers.get('authorization')
        if auth_header:
            user_info['auth_method'] = 'bearer_token' if auth_header.startswith('Bearer') else 'basic'
        
        # 세션 쿠키 확인
        session_id = request.cookies.get('session_id')
        if session_id:
            user_info['auth_method'] = 'session'
        
        # 실제 사용자 정보는 인증 시스템에서 설정된 request.state에서 가져옴
        if hasattr(request.state, 'user'):
            user = request.state.user
            user_info.update({
                'user_id': getattr(user, 'id', None),
                'username': getattr(user, 'username', None),
                'is_authenticated': True
            })
        
        return user_info
    
    def _get_request_body_size(self, request: Request) -> Optional[int]:
        """요청 본문 크기 추출"""
        content_length = request.headers.get('content-length')
        if content_length:
            try:
                return int(content_length)
            except ValueError:
                pass
        return None
    
    def _get_response_size(self, response: StarletteResponse) -> Optional[int]:
        """응답 크기 추출"""
        content_length = response.headers.get('content-length')
        if content_length:
            try:
                return int(content_length)
            except ValueError:
                pass
        return None
    
    def _handle_authentication_failure(self, db: Session, request: Request, user_info: dict):
        """인증 실패 처리"""
        ip_address = audit_service._get_client_ip(request)
        
        # 보안 이벤트 기록
        audit_service.log_security_event(
            db=db,
            event_type='AUTHENTICATION_FAILED',
            severity='MEDIUM',
            ip_address=ip_address,
            user_agent=request.headers.get('user-agent'),
            description=f"인증 실패: {request.method} {request.url.path}",
            details={
                'method': request.method,
                'path': str(request.url.path),
                'attempted_username': user_info.get('username')
            },
            source_endpoint=str(request.url.path)
        )
        
        # 연속된 실패 시도 확인 (브루트 포스 공격 감지)
        self._check_brute_force_attempt(db, ip_address)
    
    def _handle_authorization_failure(self, db: Session, request: Request, user_info: dict):
        """권한 부족 처리"""
        ip_address = audit_service._get_client_ip(request)
        
        # 보안 이벤트 기록
        audit_service.log_security_event(
            db=db,
            event_type='AUTHORIZATION_FAILED',
            severity='MEDIUM',
            ip_address=ip_address,
            user_id=user_info.get('user_id'),
            username=user_info.get('username'),
            user_agent=request.headers.get('user-agent'),
            description=f"권한 부족: {request.method} {request.url.path}",
            details={
                'method': request.method,
                'path': str(request.url.path),
                'user_id': user_info.get('user_id')
            },
            source_endpoint=str(request.url.path)
        )
    
    def _handle_server_error(self, db: Session, request: Request, user_info: dict, status_code: int, error_message: str = None):
        """서버 오류 처리"""
        ip_address = audit_service._get_client_ip(request)
        
        # 보안 이벤트 기록
        audit_service.log_security_event(
            db=db,
            event_type='SERVER_ERROR',
            severity='HIGH' if status_code >= 500 else 'MEDIUM',
            ip_address=ip_address,
            user_id=user_info.get('user_id'),
            username=user_info.get('username'),
            user_agent=request.headers.get('user-agent'),
            description=f"서버 오류 {status_code}: {request.method} {request.url.path}",
            details={
                'method': request.method,
                'path': str(request.url.path),
                'status_code': status_code,
                'error_message': error_message,
                'user_id': user_info.get('user_id')
            },
            source_endpoint=str(request.url.path)
        )
    
    def _check_brute_force_attempt(self, db: Session, ip_address: str):
        """브루트 포스 공격 시도 확인"""
        from datetime import datetime, timedelta
        from app.database import SecurityEvent
        
        # 최근 10분간 해당 IP의 인증 실패 횟수 확인
        ten_minutes_ago = datetime.utcnow() - timedelta(minutes=10)
        
        failed_attempts = db.query(SecurityEvent).filter(
            SecurityEvent.ip_address == ip_address,
            SecurityEvent.event_type == 'AUTHENTICATION_FAILED',
            SecurityEvent.created_at >= ten_minutes_ago
        ).count()
        
        # 임계값 초과 시 브루트 포스 공격으로 분류
        if failed_attempts >= audit_service.risk_thresholds['failed_login_attempts']:
            audit_service.log_security_event(
                db=db,
                event_type='BRUTE_FORCE_ATTACK',
                severity='CRITICAL',
                ip_address=ip_address,
                description=f"브루트 포스 공격 감지: {failed_attempts}회 연속 인증 실패",
                details={
                    'failed_attempts': failed_attempts,
                    'time_window': '10분',
                    'threshold': audit_service.risk_thresholds['failed_login_attempts']
                },
                auto_blocked=True
            )


class AuditActionMiddleware(BaseHTTPMiddleware):
    """사용자 액션 감사 로깅 미들웨어"""
    
    def __init__(self, app):
        super().__init__(app)
        # 감사해야 할 액션들과 리소스 타입 매핑
        self.action_mappings = {
            'POST': {
                '/api/databases': ('CREATE', 'database'),
                '/api/backups': ('BACKUP_START', 'backup'),
                '/api/schedules': ('CREATE', 'schedule'),
                '/api/users': ('CREATE', 'user'),
            },
            'PUT': {
                '/api/databases': ('UPDATE', 'database'),
                '/api/schedules': ('UPDATE', 'schedule'),
                '/api/users': ('UPDATE', 'user'),
            },
            'DELETE': {
                '/api/databases': ('DELETE', 'database'),
                '/api/backups': ('DELETE', 'backup'),
                '/api/schedules': ('DELETE', 'schedule'),
                '/api/users': ('DELETE', 'user'),
            }
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> StarletteResponse:
        """액션 감사 로깅"""
        
        # 요청 처리
        response = await call_next(request)
        
        # 성공적인 변경 작업만 감사 로그에 기록
        if response.status_code < 400 and request.method in self.action_mappings:
            await self._log_action(request, response)
        
        return response
    
    async def _log_action(self, request: Request, response: StarletteResponse):
        """액션 로그 기록"""
        method = request.method
        path = request.url.path
        
        # 경로 패턴 매칭
        action_info = None
        for pattern, (action, resource_type) in self.action_mappings[method].items():
            if path.startswith(pattern):
                action_info = (action, resource_type)
                break
        
        if not action_info:
            return
        
        action, resource_type = action_info
        
        # 사용자 정보 추출
        user_info = self._extract_user_info(request)
        if not user_info.get('user_id'):
            return  # 인증되지 않은 사용자는 감사 로그에서 제외
        
        # 리소스 ID 추출 (URL 경로에서)
        resource_id = self._extract_resource_id(path)
        
        # 요청/응답 본문에서 추가 정보 추출
        old_values, new_values, resource_name = await self._extract_change_data(request, response, action)
        
        # 감사 로그 기록
        db = next(get_db())
        try:
            audit_service.log_audit_event(
                db=db,
                user_id=user_info['user_id'],
                username=user_info['username'],
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                resource_name=resource_name,
                old_values=old_values,
                new_values=new_values,
                ip_address=audit_service._get_client_ip(request),
                user_agent=request.headers.get('user-agent'),
                session_id=request.cookies.get('session_id'),
                status='SUCCESS',
                compliance_tags=self._get_compliance_tags(action, resource_type)
            )
        finally:
            db.close()
    
    def _extract_user_info(self, request: Request) -> dict:
        """사용자 정보 추출"""
        user_info = {'user_id': None, 'username': None}
        
        if hasattr(request.state, 'user'):
            user = request.state.user
            user_info.update({
                'user_id': getattr(user, 'id', None),
                'username': getattr(user, 'username', None)
            })
        
        return user_info
    
    def _extract_resource_id(self, path: str) -> Optional[str]:
        """URL 경로에서 리소스 ID 추출"""
        import re
        
        # UUID 패턴 찾기
        uuid_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
        match = re.search(uuid_pattern, path)
        if match:
            return match.group()
        
        # 숫자 ID 패턴 찾기
        id_pattern = r'/(\d+)(?:/|$)'
        match = re.search(id_pattern, path)
        if match:
            return match.group(1)
        
        return None
    
    async def _extract_change_data(self, request: Request, response: StarletteResponse, action: str) -> tuple:
        """변경 데이터 추출"""
        old_values = None
        new_values = None
        resource_name = None
        
        # 요청 본문에서 새 값 추출 (CREATE, UPDATE 작업)
        if action in ['CREATE', 'UPDATE'] and hasattr(request, '_body'):
            try:
                body = await request.body()
                if body:
                    new_values = json.loads(body.decode('utf-8'))
                    resource_name = new_values.get('name') or new_values.get('display_name')
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
        
        # UPDATE 작업의 경우 이전 값은 별도 조회가 필요하므로 여기서는 생략
        # 실제 구현에서는 각 API 엔드포인트에서 직접 감사 로그를 기록하는 것이 더 정확함
        
        return old_values, new_values, resource_name
    
    def _get_compliance_tags(self, action: str, resource_type: str) -> List[str]:
        """규정 준수 태그 생성"""
        tags = []
        
        # 데이터 관련 작업은 GDPR 관련
        if resource_type in ['database', 'backup']:
            tags.append('GDPR')
        
        # 사용자 관련 작업은 개인정보보호 관련
        if resource_type == 'user':
            tags.extend(['GDPR', 'PRIVACY'])
        
        # 삭제 작업은 특별 관리
        if action == 'DELETE':
            tags.append('DATA_RETENTION')
        
        # 백업 관련 작업은 SOX 관련
        if resource_type == 'backup':
            tags.append('SOX')
        
        return tags
