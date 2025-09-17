"""
보안 정책 자동 적용 시스템
위험도 기반 자동 차단, 접근 제한, 알림 등
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc

from app.database import (
    SecurityEvent, AccessLog, AuditLog, get_db
)
from app.core.audit_service import audit_service


class SecurityPolicyEngine:
    """보안 정책 엔진"""
    
    def __init__(self):
        self.policies = {
            'brute_force_protection': {
                'enabled': True,
                'max_failed_attempts': 5,
                'time_window_minutes': 10,
                'block_duration_minutes': 60,
                'auto_block': True
            },
            'suspicious_activity_detection': {
                'enabled': True,
                'high_risk_threshold': 80,
                'critical_risk_threshold': 90,
                'auto_block_critical': True
            },
            'rate_limiting': {
                'enabled': True,
                'requests_per_minute': 100,
                'burst_limit': 200,
                'auto_block': True
            },
            'geo_blocking': {
                'enabled': False,
                'blocked_countries': [],
                'allowed_countries': []
            },
            'privilege_escalation_detection': {
                'enabled': True,
                'monitor_actions': ['DELETE', 'UPDATE_USER', 'BACKUP_DELETE'],
                'alert_threshold': 3
            }
        }
        
        self.blocked_ips = {}  # IP: {'blocked_until': datetime, 'reason': str}
        self.rate_limits = {}  # IP: {'requests': [], 'blocked_until': datetime}
    
    async def apply_security_policies(self, db: Session):
        """보안 정책 자동 적용"""
        
        try:
            # 브루트 포스 공격 감지 및 차단
            if self.policies['brute_force_protection']['enabled']:
                await self._detect_brute_force_attacks(db)
            
            # 의심스러운 활동 감지
            if self.policies['suspicious_activity_detection']['enabled']:
                await self._detect_suspicious_activities(db)
            
            # 권한 상승 시도 감지
            if self.policies['privilege_escalation_detection']['enabled']:
                await self._detect_privilege_escalation(db)
            
            # 차단된 IP 정리 (만료된 차단 해제)
            await self._cleanup_expired_blocks()
            
        except Exception as e:
            print(f"보안 정책 적용 중 오류: {e}")
    
    async def _detect_brute_force_attacks(self, db: Session):
        """브루트 포스 공격 감지"""
        
        policy = self.policies['brute_force_protection']
        time_window = datetime.utcnow() - timedelta(minutes=policy['time_window_minutes'])
        
        # 최근 시간 내 인증 실패가 많은 IP 조회
        failed_attempts = db.query(
            SecurityEvent.ip_address,
            func.count(SecurityEvent.id).label('attempt_count')
        ).filter(
            and_(
                SecurityEvent.event_type == 'AUTHENTICATION_FAILED',
                SecurityEvent.created_at >= time_window
            )
        ).group_by(SecurityEvent.ip_address).having(
            func.count(SecurityEvent.id) >= policy['max_failed_attempts']
        ).all()
        
        for ip_address, attempt_count in failed_attempts:
            if ip_address not in self.blocked_ips:
                # 새로운 브루트 포스 공격 감지
                await self._block_ip(
                    db=db,
                    ip_address=ip_address,
                    reason=f"브루트 포스 공격 ({attempt_count}회 실패)",
                    duration_minutes=policy['block_duration_minutes']
                )
                
                # 보안 이벤트 기록
                audit_service.log_security_event(
                    db=db,
                    event_type='BRUTE_FORCE_DETECTED',
                    severity='CRITICAL',
                    ip_address=ip_address,
                    description=f"브루트 포스 공격 감지 및 자동 차단: {attempt_count}회 연속 실패",
                    details={
                        'failed_attempts': attempt_count,
                        'time_window_minutes': policy['time_window_minutes'],
                        'block_duration_minutes': policy['block_duration_minutes']
                    },
                    auto_blocked=True
                )
    
    async def _detect_suspicious_activities(self, db: Session):
        """의심스러운 활동 감지"""
        
        policy = self.policies['suspicious_activity_detection']
        time_window = datetime.utcnow() - timedelta(hours=1)
        
        # 높은 위험도 점수를 가진 접근 로그 조회
        high_risk_accesses = db.query(AccessLog).filter(
            and_(
                AccessLog.created_at >= time_window,
                AccessLog.risk_score >= policy['high_risk_threshold']
            )
        ).all()
        
        # IP별로 그룹화하여 분석
        ip_risk_scores = {}
        for access in high_risk_accesses:
            ip = access.ip_address
            if ip not in ip_risk_scores:
                ip_risk_scores[ip] = []
            ip_risk_scores[ip].append(access.risk_score)
        
        for ip_address, scores in ip_risk_scores.items():
            avg_score = sum(scores) / len(scores)
            max_score = max(scores)
            
            # 임계 위험도 초과 시 자동 차단
            if max_score >= policy['critical_risk_threshold'] and policy['auto_block_critical']:
                if ip_address not in self.blocked_ips:
                    await self._block_ip(
                        db=db,
                        ip_address=ip_address,
                        reason=f"임계 위험도 초과 (최대: {max_score}, 평균: {avg_score:.1f})",
                        duration_minutes=120
                    )
                    
                    audit_service.log_security_event(
                        db=db,
                        event_type='HIGH_RISK_ACTIVITY',
                        severity='CRITICAL',
                        ip_address=ip_address,
                        description=f"임계 위험도 활동 감지 및 자동 차단",
                        details={
                            'max_risk_score': max_score,
                            'avg_risk_score': avg_score,
                            'access_count': len(scores)
                        },
                        auto_blocked=True
                    )
            
            # 높은 위험도 경고
            elif avg_score >= policy['high_risk_threshold']:
                audit_service.log_security_event(
                    db=db,
                    event_type='SUSPICIOUS_ACTIVITY',
                    severity='HIGH',
                    ip_address=ip_address,
                    description=f"의심스러운 활동 패턴 감지",
                    details={
                        'max_risk_score': max_score,
                        'avg_risk_score': avg_score,
                        'access_count': len(scores)
                    }
                )
    
    async def _detect_privilege_escalation(self, db: Session):
        """권한 상승 시도 감지"""
        
        policy = self.policies['privilege_escalation_detection']
        time_window = datetime.utcnow() - timedelta(hours=1)
        
        # 고권한 작업 수행 이력 조회
        privilege_actions = db.query(AuditLog).filter(
            and_(
                AuditLog.created_at >= time_window,
                AuditLog.action.in_(policy['monitor_actions'])
            )
        ).all()
        
        # 사용자별로 그룹화
        user_actions = {}
        for action in privilege_actions:
            user_id = action.user_id
            if user_id not in user_actions:
                user_actions[user_id] = []
            user_actions[user_id].append(action)
        
        for user_id, actions in user_actions.items():
            if len(actions) >= policy['alert_threshold']:
                # 권한 상승 시도 의심
                audit_service.log_security_event(
                    db=db,
                    event_type='PRIVILEGE_ESCALATION_ATTEMPT',
                    severity='HIGH',
                    user_id=user_id,
                    username=actions[0].username,
                    ip_address=actions[0].ip_address,
                    description=f"권한 상승 시도 의심: {len(actions)}회 고권한 작업",
                    details={
                        'actions': [a.action for a in actions],
                        'action_count': len(actions),
                        'time_window_hours': 1
                    }
                )
    
    async def _block_ip(
        self,
        db: Session,
        ip_address: str,
        reason: str,
        duration_minutes: int
    ):
        """IP 주소 차단"""
        
        blocked_until = datetime.utcnow() + timedelta(minutes=duration_minutes)
        
        self.blocked_ips[ip_address] = {
            'blocked_until': blocked_until,
            'reason': reason,
            'blocked_at': datetime.utcnow()
        }
        
        print(f"IP 차단: {ip_address} - {reason} (해제: {blocked_until})")
    
    async def _cleanup_expired_blocks(self):
        """만료된 차단 정리"""
        
        now = datetime.utcnow()
        expired_ips = [
            ip for ip, info in self.blocked_ips.items()
            if info['blocked_until'] <= now
        ]
        
        for ip in expired_ips:
            del self.blocked_ips[ip]
            print(f"IP 차단 해제: {ip}")
    
    def is_ip_blocked(self, ip_address: str) -> tuple[bool, Optional[str]]:
        """IP 차단 여부 확인"""
        
        if ip_address in self.blocked_ips:
            block_info = self.blocked_ips[ip_address]
            if block_info['blocked_until'] > datetime.utcnow():
                return True, block_info['reason']
            else:
                # 만료된 차단 제거
                del self.blocked_ips[ip_address]
        
        return False, None
    
    def check_rate_limit(self, ip_address: str) -> tuple[bool, Optional[str]]:
        """속도 제한 확인"""
        
        if not self.policies['rate_limiting']['enabled']:
            return False, None
        
        now = datetime.utcnow()
        policy = self.policies['rate_limiting']
        
        # IP별 요청 기록 초기화
        if ip_address not in self.rate_limits:
            self.rate_limits[ip_address] = {
                'requests': [],
                'blocked_until': None
            }
        
        rate_info = self.rate_limits[ip_address]
        
        # 기존 차단 확인
        if rate_info['blocked_until'] and rate_info['blocked_until'] > now:
            return True, "속도 제한 초과로 인한 차단"
        
        # 1분 이내 요청 기록 정리
        one_minute_ago = now - timedelta(minutes=1)
        rate_info['requests'] = [
            req_time for req_time in rate_info['requests']
            if req_time > one_minute_ago
        ]
        
        # 현재 요청 추가
        rate_info['requests'].append(now)
        
        # 속도 제한 확인
        if len(rate_info['requests']) > policy['requests_per_minute']:
            # 속도 제한 초과 - 10분 차단
            rate_info['blocked_until'] = now + timedelta(minutes=10)
            return True, f"분당 {policy['requests_per_minute']}회 요청 제한 초과"
        
        return False, None
    
    def get_security_status(self) -> Dict[str, Any]:
        """보안 상태 조회"""
        
        now = datetime.utcnow()
        active_blocks = {
            ip: info for ip, info in self.blocked_ips.items()
            if info['blocked_until'] > now
        }
        
        return {
            'policies': self.policies,
            'active_blocks': len(active_blocks),
            'blocked_ips': [
                {
                    'ip_address': ip,
                    'reason': info['reason'],
                    'blocked_at': info['blocked_at'].isoformat(),
                    'blocked_until': info['blocked_until'].isoformat()
                }
                for ip, info in active_blocks.items()
            ],
            'rate_limits': {
                ip: {
                    'recent_requests': len(info['requests']),
                    'blocked_until': info['blocked_until'].isoformat() if info['blocked_until'] else None
                }
                for ip, info in self.rate_limits.items()
            }
        }
    
    def update_policy(self, policy_name: str, policy_config: Dict[str, Any]):
        """보안 정책 업데이트"""
        
        if policy_name in self.policies:
            self.policies[policy_name].update(policy_config)
            return True
        return False
    
    def unblock_ip(self, ip_address: str) -> bool:
        """IP 차단 해제"""
        
        if ip_address in self.blocked_ips:
            del self.blocked_ips[ip_address]
            return True
        return False


# 전역 보안 정책 엔진 인스턴스
security_policy_engine = SecurityPolicyEngine()


# 백그라운드 작업으로 주기적 보안 정책 적용
async def run_security_policy_monitor():
    """보안 정책 모니터링 백그라운드 작업"""
    
    while True:
        try:
            db = next(get_db())
            try:
                await security_policy_engine.apply_security_policies(db)
            finally:
                db.close()
            
            # 5분마다 실행
            await asyncio.sleep(300)
            
        except Exception as e:
            print(f"보안 정책 모니터링 오류: {e}")
            await asyncio.sleep(60)  # 오류 시 1분 후 재시도
