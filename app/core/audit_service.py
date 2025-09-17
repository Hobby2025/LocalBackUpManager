"""
감사 시스템 서비스
사용자 행동 추적, 접근 로그, 보안 이벤트 관리
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func
from fastapi import Request
import hashlib
import ipaddress

from app.database import (
    AuditLog, AccessLog, SecurityEvent, ComplianceReport,
    get_db
)


class AuditService:
    """감사 로그 및 보안 이벤트 관리 서비스"""
    
    def __init__(self):
        self.risk_thresholds = {
            'failed_login_attempts': 5,
            'suspicious_ip_score': 70,
            'high_privilege_actions': ['DELETE', 'UPDATE_USER', 'BACKUP_DELETE'],
            'blocked_countries': [],  # 설정에서 로드
            'rate_limit_per_minute': 100
        }
    
    def log_audit_event(
        self,
        db: Session,
        user_id: str,
        username: str,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        resource_name: Optional[str] = None,
        old_values: Optional[Dict] = None,
        new_values: Optional[Dict] = None,
        ip_address: str = "127.0.0.1",
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        status: str = "SUCCESS",
        error_message: Optional[str] = None,
        duration_ms: Optional[int] = None,
        compliance_tags: Optional[List[str]] = None
    ) -> AuditLog:
        """감사 로그 기록"""
        
        # 규정 준수 태그 처리
        compliance_data = {}
        if compliance_tags:
            compliance_data = {
                'tags': compliance_tags,
                'gdpr_relevant': 'GDPR' in compliance_tags,
                'sox_relevant': 'SOX' in compliance_tags,
                'hipaa_relevant': 'HIPAA' in compliance_tags
            }
        
        audit_log = AuditLog(
            user_id=user_id,
            username=username,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            old_values=old_values,
            new_values=new_values,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            request_id=request_id,
            status=status,
            error_message=error_message,
            duration_ms=duration_ms,
            compliance_tags=compliance_data
        )
        
        db.add(audit_log)
        db.commit()
        db.refresh(audit_log)
        
        # 고위험 작업인 경우 보안 이벤트도 생성
        if action in self.risk_thresholds['high_privilege_actions']:
            self.log_security_event(
                db=db,
                event_type='HIGH_PRIVILEGE_ACTION',
                severity='MEDIUM',
                user_id=user_id,
                username=username,
                ip_address=ip_address,
                description=f"고권한 작업 수행: {action} on {resource_type}",
                details={'audit_log_id': audit_log.id, 'action': action, 'resource_type': resource_type}
            )
        
        return audit_log
    
    def log_access(
        self,
        db: Session,
        request: Request,
        response_status: int,
        response_size: Optional[int] = None,
        response_time_ms: Optional[int] = None,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        is_authenticated: bool = False,
        auth_method: Optional[str] = None
    ) -> AccessLog:
        """API 접근 로그 기록"""
        
        # 클라이언트 IP 주소 추출
        ip_address = self._get_client_ip(request)
        
        # 위험도 점수 계산
        risk_score = self._calculate_risk_score(ip_address, request.url.path, request.method)
        
        # 차단 여부 결정
        blocked = risk_score >= self.risk_thresholds['suspicious_ip_score']
        block_reason = None
        if blocked:
            block_reason = f"위험도 점수 {risk_score}로 인한 자동 차단"
        
        access_log = AccessLog(
            user_id=user_id,
            username=username,
            method=request.method,
            endpoint=self._extract_endpoint(request.url.path),
            path=str(request.url.path),
            query_params=dict(request.query_params) if request.query_params else None,
            request_body_size=self._get_request_body_size(request),
            response_status=response_status,
            response_size=response_size,
            response_time_ms=response_time_ms,
            ip_address=ip_address,
            user_agent=request.headers.get('user-agent'),
            referer=request.headers.get('referer'),
            session_id=self._extract_session_id(request),
            request_id=str(uuid.uuid4()),
            is_authenticated=is_authenticated,
            auth_method=auth_method,
            risk_score=risk_score,
            blocked=blocked,
            block_reason=block_reason
        )
        
        db.add(access_log)
        db.commit()
        db.refresh(access_log)
        
        # 높은 위험도인 경우 보안 이벤트 생성
        if risk_score >= 80:
            self.log_security_event(
                db=db,
                event_type='HIGH_RISK_ACCESS',
                severity='HIGH',
                user_id=user_id,
                username=username,
                ip_address=ip_address,
                description=f"높은 위험도 접근 감지 (점수: {risk_score})",
                details={'access_log_id': access_log.id, 'risk_score': risk_score}
            )
        
        return access_log
    
    def log_security_event(
        self,
        db: Session,
        event_type: str,
        severity: str,
        ip_address: str,
        description: str,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict] = None,
        source_endpoint: Optional[str] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        auto_blocked: bool = False
    ) -> SecurityEvent:
        """보안 이벤트 로그 기록"""
        
        security_event = SecurityEvent(
            event_type=event_type,
            severity=severity,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            description=description,
            details=details,
            source_endpoint=source_endpoint,
            session_id=session_id,
            request_id=request_id,
            auto_blocked=auto_blocked
        )
        
        db.add(security_event)
        db.commit()
        db.refresh(security_event)
        
        return security_event
    
    def get_audit_logs(
        self,
        db: Session,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditLog]:
        """감사 로그 조회"""
        
        query = db.query(AuditLog)
        
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        if action:
            query = query.filter(AuditLog.action == action)
        if resource_type:
            query = query.filter(AuditLog.resource_type == resource_type)
        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)
        
        return query.order_by(desc(AuditLog.created_at)).offset(offset).limit(limit).all()
    
    def get_access_logs(
        self,
        db: Session,
        ip_address: Optional[str] = None,
        endpoint: Optional[str] = None,
        user_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AccessLog]:
        """접근 로그 조회"""
        
        query = db.query(AccessLog)
        
        if ip_address:
            query = query.filter(AccessLog.ip_address == ip_address)
        if endpoint:
            query = query.filter(AccessLog.endpoint.like(f"%{endpoint}%"))
        if user_id:
            query = query.filter(AccessLog.user_id == user_id)
        if start_date:
            query = query.filter(AccessLog.created_at >= start_date)
        if end_date:
            query = query.filter(AccessLog.created_at <= end_date)
        
        return query.order_by(desc(AccessLog.created_at)).offset(offset).limit(limit).all()
    
    def get_security_events(
        self,
        db: Session,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        resolved: Optional[bool] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[SecurityEvent]:
        """보안 이벤트 조회"""
        
        query = db.query(SecurityEvent)
        
        if event_type:
            query = query.filter(SecurityEvent.event_type == event_type)
        if severity:
            query = query.filter(SecurityEvent.severity == severity)
        if resolved is not None:
            query = query.filter(SecurityEvent.resolved == resolved)
        if start_date:
            query = query.filter(SecurityEvent.created_at >= start_date)
        if end_date:
            query = query.filter(SecurityEvent.created_at <= end_date)
        
        return query.order_by(desc(SecurityEvent.created_at)).offset(offset).limit(limit).all()
    
    def resolve_security_event(
        self,
        db: Session,
        event_id: str,
        resolved_by: str,
        resolution_notes: Optional[str] = None
    ) -> Optional[SecurityEvent]:
        """보안 이벤트 해결 처리"""
        
        event = db.query(SecurityEvent).filter(SecurityEvent.id == event_id).first()
        if not event:
            return None
        
        event.resolved = True
        event.resolved_by = resolved_by
        event.resolved_at = datetime.utcnow()
        event.resolution_notes = resolution_notes
        
        db.commit()
        db.refresh(event)
        
        return event
    
    def get_audit_statistics(
        self,
        db: Session,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """감사 통계 조회"""
        
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        
        # 기본 통계
        total_audit_logs = db.query(AuditLog).filter(
            and_(AuditLog.created_at >= start_date, AuditLog.created_at <= end_date)
        ).count()
        
        total_access_logs = db.query(AccessLog).filter(
            and_(AccessLog.created_at >= start_date, AccessLog.created_at <= end_date)
        ).count()
        
        total_security_events = db.query(SecurityEvent).filter(
            and_(SecurityEvent.created_at >= start_date, SecurityEvent.created_at <= end_date)
        ).count()
        
        # 액션별 통계
        action_stats = db.query(
            AuditLog.action,
            func.count(AuditLog.id).label('count')
        ).filter(
            and_(AuditLog.created_at >= start_date, AuditLog.created_at <= end_date)
        ).group_by(AuditLog.action).all()
        
        # 사용자별 통계
        user_stats = db.query(
            AuditLog.username,
            func.count(AuditLog.id).label('count')
        ).filter(
            and_(AuditLog.created_at >= start_date, AuditLog.created_at <= end_date)
        ).group_by(AuditLog.username).order_by(desc('count')).limit(10).all()
        
        # IP별 접근 통계
        ip_stats = db.query(
            AccessLog.ip_address,
            func.count(AccessLog.id).label('count'),
            func.avg(AccessLog.risk_score).label('avg_risk_score')
        ).filter(
            and_(AccessLog.created_at >= start_date, AccessLog.created_at <= end_date)
        ).group_by(AccessLog.ip_address).order_by(desc('count')).limit(10).all()
        
        return {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'totals': {
                'audit_logs': total_audit_logs,
                'access_logs': total_access_logs,
                'security_events': total_security_events
            },
            'action_statistics': [{'action': row.action, 'count': row.count} for row in action_stats],
            'user_statistics': [{'username': row.username, 'count': row.count} for row in user_stats],
            'ip_statistics': [
                {
                    'ip_address': row.ip_address,
                    'count': row.count,
                    'avg_risk_score': float(row.avg_risk_score) if row.avg_risk_score else 0
                }
                for row in ip_stats
            ]
        }
    
    def _get_client_ip(self, request: Request) -> str:
        """클라이언트 IP 주소 추출"""
        # X-Forwarded-For 헤더 확인 (프록시/로드밸런서 환경)
        forwarded_for = request.headers.get('x-forwarded-for')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        # X-Real-IP 헤더 확인
        real_ip = request.headers.get('x-real-ip')
        if real_ip:
            return real_ip
        
        # 직접 연결된 클라이언트 IP
        return request.client.host if request.client else "127.0.0.1"
    
    def _extract_endpoint(self, path: str) -> str:
        """경로에서 엔드포인트 패턴 추출"""
        # UUID나 숫자 ID를 {id}로 치환하여 패턴화
        import re
        
        # UUID 패턴 치환
        path = re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '/{id}', path)
        
        # 숫자 ID 패턴 치환
        path = re.sub(r'/\d+', '/{id}', path)
        
        return path
    
    def _get_request_body_size(self, request: Request) -> Optional[int]:
        """요청 본문 크기 추출"""
        content_length = request.headers.get('content-length')
        if content_length:
            try:
                return int(content_length)
            except ValueError:
                pass
        return None
    
    def _extract_session_id(self, request: Request) -> Optional[str]:
        """세션 ID 추출"""
        # 쿠키에서 세션 ID 추출
        return request.cookies.get('session_id')
    
    def _calculate_risk_score(self, ip_address: str, path: str, method: str) -> int:
        """위험도 점수 계산"""
        score = 0
        
        # IP 주소 기반 위험도
        try:
            ip = ipaddress.ip_address(ip_address)
            if ip.is_private:
                score += 0  # 내부 IP는 안전
            elif ip.is_loopback:
                score += 0  # 로컬호스트는 안전
            else:
                score += 20  # 외부 IP는 기본 위험도
        except ValueError:
            score += 50  # 잘못된 IP 형식은 높은 위험도
        
        # 경로 기반 위험도
        high_risk_paths = ['/api/users', '/api/databases', '/api/backups']
        if any(path.startswith(risk_path) for risk_path in high_risk_paths):
            score += 30
        
        # HTTP 메서드 기반 위험도
        if method in ['DELETE']:
            score += 40
        elif method in ['POST', 'PUT', 'PATCH']:
            score += 20
        
        return min(score, 100)  # 최대 100점


# 전역 감사 서비스 인스턴스
audit_service = AuditService()
