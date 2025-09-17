"""
감사 로그 및 보안 이벤트 API 엔드포인트
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.database import get_db
from app.core.audit_service import audit_service
from app.database import AuditLog, AccessLog, SecurityEvent, ComplianceReport


router = APIRouter(prefix="/api/audit", tags=["audit"])


# Pydantic 모델 정의
class AuditLogResponse(BaseModel):
    """감사 로그 응답 모델"""
    id: str
    user_id: str
    username: str
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    resource_name: Optional[str] = None
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    ip_address: str
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None
    compliance_tags: Optional[Dict[str, Any]] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class AccessLogResponse(BaseModel):
    """접근 로그 응답 모델"""
    id: str
    user_id: Optional[str] = None
    username: Optional[str] = None
    method: str
    endpoint: str
    path: str
    query_params: Optional[Dict[str, Any]] = None
    request_body_size: Optional[int] = None
    response_status: int
    response_size: Optional[int] = None
    response_time_ms: Optional[int] = None
    ip_address: str
    user_agent: Optional[str] = None
    referer: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    is_authenticated: bool
    auth_method: Optional[str] = None
    risk_score: int
    blocked: bool
    block_reason: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class SecurityEventResponse(BaseModel):
    """보안 이벤트 응답 모델"""
    id: str
    event_type: str
    severity: str
    user_id: Optional[str] = None
    username: Optional[str] = None
    ip_address: str
    user_agent: Optional[str] = None
    description: str
    details: Optional[Dict[str, Any]] = None
    source_endpoint: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    resolved: bool
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    auto_blocked: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class SecurityEventResolveRequest(BaseModel):
    """보안 이벤트 해결 요청 모델"""
    resolution_notes: Optional[str] = Field(None, description="해결 메모")


class AuditStatisticsResponse(BaseModel):
    """감사 통계 응답 모델"""
    period: Dict[str, str]
    totals: Dict[str, int]
    action_statistics: List[Dict[str, Any]]
    user_statistics: List[Dict[str, Any]]
    ip_statistics: List[Dict[str, Any]]


class ComplianceReportResponse(BaseModel):
    """규정 준수 리포트 응답 모델"""
    id: str
    report_type: str
    period_start: datetime
    period_end: datetime
    generated_by: str
    status: str
    total_events: int
    compliant_events: int
    non_compliant_events: int
    compliance_score: Optional[float] = None
    findings: Optional[Dict[str, Any]] = None
    recommendations: Optional[Dict[str, Any]] = None
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# API 엔드포인트
@router.get("/logs", response_model=List[AuditLogResponse])
async def get_audit_logs(
    user_id: Optional[str] = Query(None, description="사용자 ID로 필터링"),
    action: Optional[str] = Query(None, description="액션으로 필터링"),
    resource_type: Optional[str] = Query(None, description="리소스 타입으로 필터링"),
    start_date: Optional[datetime] = Query(None, description="시작 날짜"),
    end_date: Optional[datetime] = Query(None, description="종료 날짜"),
    limit: int = Query(100, ge=1, le=1000, description="조회 개수"),
    offset: int = Query(0, ge=0, description="오프셋"),
    db: Session = Depends(get_db)
):
    """감사 로그 조회"""
    
    logs = audit_service.get_audit_logs(
        db=db,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset
    )
    
    return logs


@router.get("/access-logs", response_model=List[AccessLogResponse])
async def get_access_logs(
    ip_address: Optional[str] = Query(None, description="IP 주소로 필터링"),
    endpoint: Optional[str] = Query(None, description="엔드포인트로 필터링"),
    user_id: Optional[str] = Query(None, description="사용자 ID로 필터링"),
    start_date: Optional[datetime] = Query(None, description="시작 날짜"),
    end_date: Optional[datetime] = Query(None, description="종료 날짜"),
    limit: int = Query(100, ge=1, le=1000, description="조회 개수"),
    offset: int = Query(0, ge=0, description="오프셋"),
    db: Session = Depends(get_db)
):
    """접근 로그 조회"""
    
    logs = audit_service.get_access_logs(
        db=db,
        ip_address=ip_address,
        endpoint=endpoint,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset
    )
    
    return logs


@router.get("/security-events", response_model=List[SecurityEventResponse])
async def get_security_events(
    event_type: Optional[str] = Query(None, description="이벤트 타입으로 필터링"),
    severity: Optional[str] = Query(None, description="심각도로 필터링 (LOW, MEDIUM, HIGH, CRITICAL)"),
    resolved: Optional[bool] = Query(None, description="해결 여부로 필터링"),
    start_date: Optional[datetime] = Query(None, description="시작 날짜"),
    end_date: Optional[datetime] = Query(None, description="종료 날짜"),
    limit: int = Query(100, ge=1, le=1000, description="조회 개수"),
    offset: int = Query(0, ge=0, description="오프셋"),
    db: Session = Depends(get_db)
):
    """보안 이벤트 조회"""
    
    events = audit_service.get_security_events(
        db=db,
        event_type=event_type,
        severity=severity,
        resolved=resolved,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset
    )
    
    return events


@router.post("/security-events/{event_id}/resolve", response_model=SecurityEventResponse)
async def resolve_security_event(
    event_id: str = Path(..., description="보안 이벤트 ID"),
    request: SecurityEventResolveRequest = None,
    db: Session = Depends(get_db)
):
    """보안 이벤트 해결 처리"""
    
    # TODO: 현재 사용자 정보 가져오기 (인증 시스템 연동 후)
    resolved_by = "admin"  # 임시값
    
    event = audit_service.resolve_security_event(
        db=db,
        event_id=event_id,
        resolved_by=resolved_by,
        resolution_notes=request.resolution_notes if request else None
    )
    
    if not event:
        raise HTTPException(status_code=404, detail="보안 이벤트를 찾을 수 없습니다")
    
    return event


@router.get("/statistics", response_model=AuditStatisticsResponse)
async def get_audit_statistics(
    start_date: Optional[datetime] = Query(None, description="시작 날짜"),
    end_date: Optional[datetime] = Query(None, description="종료 날짜"),
    db: Session = Depends(get_db)
):
    """감사 통계 조회"""
    
    statistics = audit_service.get_audit_statistics(
        db=db,
        start_date=start_date,
        end_date=end_date
    )
    
    return statistics


@router.get("/compliance-reports", response_model=List[ComplianceReportResponse])
async def get_compliance_reports(
    report_type: Optional[str] = Query(None, description="리포트 타입으로 필터링"),
    status: Optional[str] = Query(None, description="상태로 필터링"),
    limit: int = Query(50, ge=1, le=200, description="조회 개수"),
    offset: int = Query(0, ge=0, description="오프셋"),
    db: Session = Depends(get_db)
):
    """규정 준수 리포트 목록 조회"""
    
    query = db.query(ComplianceReport)
    
    if report_type:
        query = query.filter(ComplianceReport.report_type == report_type)
    if status:
        query = query.filter(ComplianceReport.status == status)
    
    reports = query.order_by(ComplianceReport.created_at.desc()).offset(offset).limit(limit).all()
    
    return reports


@router.post("/compliance-reports", response_model=ComplianceReportResponse)
async def generate_compliance_report(
    report_type: str = Query(..., description="리포트 타입 (GDPR, SOX, HIPAA, PCI_DSS)"),
    period_start: datetime = Query(..., description="보고 기간 시작"),
    period_end: datetime = Query(..., description="보고 기간 종료"),
    db: Session = Depends(get_db)
):
    """규정 준수 리포트 생성"""
    
    # TODO: 현재 사용자 정보 가져오기
    generated_by = "admin"  # 임시값
    
    # 리포트 레코드 생성
    report = ComplianceReport(
        report_type=report_type,
        period_start=period_start,
        period_end=period_end,
        generated_by=generated_by,
        status='GENERATING'
    )
    
    db.add(report)
    db.commit()
    db.refresh(report)
    
    # TODO: 백그라운드 작업으로 실제 리포트 생성 처리
    # 현재는 기본 구조만 생성
    
    return report


@router.get("/compliance-reports/{report_id}", response_model=ComplianceReportResponse)
async def get_compliance_report(
    report_id: str = Path(..., description="리포트 ID"),
    db: Session = Depends(get_db)
):
    """규정 준수 리포트 상세 조회"""
    
    report = db.query(ComplianceReport).filter(ComplianceReport.id == report_id).first()
    
    if not report:
        raise HTTPException(status_code=404, detail="리포트를 찾을 수 없습니다")
    
    return report


@router.get("/dashboard")
async def get_audit_dashboard(
    db: Session = Depends(get_db)
):
    """감사 대시보드 데이터 조회"""
    
    # 최근 24시간 통계
    yesterday = datetime.utcnow() - timedelta(days=1)
    
    # 기본 통계
    recent_audit_logs = db.query(AuditLog).filter(AuditLog.created_at >= yesterday).count()
    recent_access_logs = db.query(AccessLog).filter(AccessLog.created_at >= yesterday).count()
    recent_security_events = db.query(SecurityEvent).filter(SecurityEvent.created_at >= yesterday).count()
    unresolved_security_events = db.query(SecurityEvent).filter(SecurityEvent.resolved == False).count()
    
    # 상위 위험 IP 주소
    from sqlalchemy import func, desc
    top_risk_ips = db.query(
        AccessLog.ip_address,
        func.avg(AccessLog.risk_score).label('avg_risk_score'),
        func.count(AccessLog.id).label('access_count')
    ).filter(
        AccessLog.created_at >= yesterday
    ).group_by(AccessLog.ip_address).order_by(desc('avg_risk_score')).limit(5).all()
    
    # 최근 보안 이벤트
    recent_events = db.query(SecurityEvent).filter(
        SecurityEvent.created_at >= yesterday
    ).order_by(desc(SecurityEvent.created_at)).limit(10).all()
    
    # 액션별 통계
    action_stats = db.query(
        AuditLog.action,
        func.count(AuditLog.id).label('count')
    ).filter(
        AuditLog.created_at >= yesterday
    ).group_by(AuditLog.action).order_by(desc('count')).limit(10).all()
    
    return {
        'summary': {
            'recent_audit_logs': recent_audit_logs,
            'recent_access_logs': recent_access_logs,
            'recent_security_events': recent_security_events,
            'unresolved_security_events': unresolved_security_events
        },
        'top_risk_ips': [
            {
                'ip_address': row.ip_address,
                'avg_risk_score': float(row.avg_risk_score),
                'access_count': row.access_count
            }
            for row in top_risk_ips
        ],
        'recent_security_events': [
            {
                'id': event.id,
                'event_type': event.event_type,
                'severity': event.severity,
                'description': event.description,
                'created_at': event.created_at.isoformat()
            }
            for event in recent_events
        ],
        'action_statistics': [
            {
                'action': row.action,
                'count': row.count
            }
            for row in action_stats
        ]
    }


@router.get("/export/audit-logs")
async def export_audit_logs(
    format: str = Query("csv", description="내보내기 형식 (csv, json)"),
    start_date: Optional[datetime] = Query(None, description="시작 날짜"),
    end_date: Optional[datetime] = Query(None, description="종료 날짜"),
    db: Session = Depends(get_db)
):
    """감사 로그 내보내기"""
    
    # TODO: 실제 내보내기 기능 구현
    # CSV 또는 JSON 형식으로 감사 로그 데이터 내보내기
    
    return {"message": "내보내기 기능은 구현 예정입니다"}


@router.get("/search")
async def search_audit_logs(
    query: str = Query(..., description="검색 쿼리"),
    search_type: str = Query("all", description="검색 타입 (audit, access, security, all)"),
    limit: int = Query(100, ge=1, le=1000, description="조회 개수"),
    db: Session = Depends(get_db)
):
    """감사 로그 통합 검색"""
    
    results = {
        'audit_logs': [],
        'access_logs': [],
        'security_events': []
    }
    
    if search_type in ['audit', 'all']:
        # 감사 로그 검색
        audit_logs = db.query(AuditLog).filter(
            AuditLog.message.ilike(f"%{query}%") |
            AuditLog.username.ilike(f"%{query}%") |
            AuditLog.action.ilike(f"%{query}%")
        ).limit(limit).all()
        results['audit_logs'] = audit_logs
    
    if search_type in ['access', 'all']:
        # 접근 로그 검색
        access_logs = db.query(AccessLog).filter(
            AccessLog.endpoint.ilike(f"%{query}%") |
            AccessLog.ip_address.ilike(f"%{query}%") |
            AccessLog.username.ilike(f"%{query}%")
        ).limit(limit).all()
        results['access_logs'] = access_logs
    
    if search_type in ['security', 'all']:
        # 보안 이벤트 검색
        security_events = db.query(SecurityEvent).filter(
            SecurityEvent.description.ilike(f"%{query}%") |
            SecurityEvent.event_type.ilike(f"%{query}%") |
            SecurityEvent.ip_address.ilike(f"%{query}%")
        ).limit(limit).all()
        results['security_events'] = security_events
    
    return results
