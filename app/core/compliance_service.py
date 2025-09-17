"""
규정 준수 리포트 생성 서비스
GDPR, SOX, HIPAA 등 다양한 규정 준수 리포트 생성
"""

import json
import csv
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc
from pathlib import Path

from app.database import (
    AuditLog, AccessLog, SecurityEvent, ComplianceReport,
    get_db
)


class ComplianceService:
    """규정 준수 리포트 생성 서비스"""
    
    def __init__(self):
        self.report_generators = {
            'GDPR': self._generate_gdpr_report,
            'SOX': self._generate_sox_report,
            'HIPAA': self._generate_hipaa_report,
            'PCI_DSS': self._generate_pci_dss_report
        }
        
        self.compliance_rules = {
            'GDPR': {
                'data_access_tracking': True,
                'data_modification_tracking': True,
                'data_deletion_tracking': True,
                'user_consent_tracking': True,
                'breach_notification': True
            },
            'SOX': {
                'financial_data_access': True,
                'change_management': True,
                'access_controls': True,
                'audit_trail': True
            },
            'HIPAA': {
                'phi_access_tracking': True,
                'minimum_necessary': True,
                'audit_controls': True,
                'integrity_controls': True
            }
        }
    
    def generate_compliance_report(
        self,
        db: Session,
        report_type: str,
        period_start: datetime,
        period_end: datetime,
        generated_by: str
    ) -> ComplianceReport:
        """규정 준수 리포트 생성"""
        
        if report_type not in self.report_generators:
            raise ValueError(f"지원하지 않는 리포트 타입: {report_type}")
        
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
        
        try:
            # 리포트 생성
            report_data = self.report_generators[report_type](
                db, period_start, period_end
            )
            
            # 리포트 파일 저장
            file_path = self._save_report_file(report.id, report_type, report_data)
            
            # 리포트 완료 처리
            report.status = 'COMPLETED'
            report.total_events = report_data['summary']['total_events']
            report.compliant_events = report_data['summary']['compliant_events']
            report.non_compliant_events = report_data['summary']['non_compliant_events']
            report.compliance_score = report_data['summary']['compliance_score']
            report.findings = report_data['findings']
            report.recommendations = report_data['recommendations']
            report.file_path = file_path
            report.file_size = Path(file_path).stat().st_size if Path(file_path).exists() else 0
            report.completed_at = datetime.utcnow()
            
            db.commit()
            
        except Exception as e:
            # 오류 발생 시 실패 처리
            report.status = 'FAILED'
            db.commit()
            raise e
        
        return report
    
    def _generate_gdpr_report(
        self,
        db: Session,
        period_start: datetime,
        period_end: datetime
    ) -> Dict[str, Any]:
        """GDPR 준수 리포트 생성"""
        
        # 개인정보 관련 이벤트 조회
        gdpr_events = db.query(AuditLog).filter(
            and_(
                AuditLog.created_at >= period_start,
                AuditLog.created_at <= period_end,
                AuditLog.compliance_tags.op('?')('gdpr_relevant')
            )
        ).all()
        
        # 데이터 접근 추적
        data_access_events = [e for e in gdpr_events if e.action in ['READ', 'VIEW', 'EXPORT']]
        
        # 데이터 수정 추적
        data_modification_events = [e for e in gdpr_events if e.action in ['CREATE', 'UPDATE']]
        
        # 데이터 삭제 추적
        data_deletion_events = [e for e in gdpr_events if e.action == 'DELETE']
        
        # 보안 이벤트 조회
        security_events = db.query(SecurityEvent).filter(
            and_(
                SecurityEvent.created_at >= period_start,
                SecurityEvent.created_at <= period_end
            )
        ).all()
        
        # 준수 점수 계산
        total_events = len(gdpr_events)
        compliant_events = len([e for e in gdpr_events if e.status == 'SUCCESS'])
        compliance_score = (compliant_events / total_events * 100) if total_events > 0 else 100
        
        # 발견사항
        findings = []
        if len(data_deletion_events) == 0:
            findings.append({
                'type': 'WARNING',
                'message': '기간 내 데이터 삭제 이벤트가 없습니다',
                'recommendation': '데이터 보존 정책 검토 필요'
            })
        
        # 권장사항
        recommendations = [
            '정기적인 개인정보 처리 현황 점검',
            '데이터 주체 권리 행사 절차 개선',
            '개인정보 보호 교육 실시'
        ]
        
        return {
            'summary': {
                'total_events': total_events,
                'compliant_events': compliant_events,
                'non_compliant_events': total_events - compliant_events,
                'compliance_score': compliance_score
            },
            'details': {
                'data_access_events': len(data_access_events),
                'data_modification_events': len(data_modification_events),
                'data_deletion_events': len(data_deletion_events),
                'security_events': len(security_events)
            },
            'findings': findings,
            'recommendations': recommendations
        }
    
    def _generate_sox_report(
        self,
        db: Session,
        period_start: datetime,
        period_end: datetime
    ) -> Dict[str, Any]:
        """SOX 준수 리포트 생성"""
        
        # 재무 데이터 관련 이벤트 조회
        sox_events = db.query(AuditLog).filter(
            and_(
                AuditLog.created_at >= period_start,
                AuditLog.created_at <= period_end,
                AuditLog.compliance_tags.op('?')('sox_relevant')
            )
        ).all()
        
        # 백업 관련 이벤트 (재무 데이터 보호)
        backup_events = [e for e in sox_events if e.resource_type == 'backup']
        
        # 접근 제어 이벤트
        access_control_events = db.query(SecurityEvent).filter(
            and_(
                SecurityEvent.created_at >= period_start,
                SecurityEvent.created_at <= period_end,
                SecurityEvent.event_type.in_(['AUTHORIZATION_FAILED', 'PRIVILEGE_ESCALATION'])
            )
        ).all()
        
        total_events = len(sox_events)
        compliant_events = len([e for e in sox_events if e.status == 'SUCCESS'])
        compliance_score = (compliant_events / total_events * 100) if total_events > 0 else 100
        
        findings = []
        recommendations = [
            '정기적인 백업 검증 수행',
            '접근 권한 정기 검토',
            '변경 관리 프로세스 강화'
        ]
        
        return {
            'summary': {
                'total_events': total_events,
                'compliant_events': compliant_events,
                'non_compliant_events': total_events - compliant_events,
                'compliance_score': compliance_score
            },
            'details': {
                'backup_events': len(backup_events),
                'access_control_events': len(access_control_events)
            },
            'findings': findings,
            'recommendations': recommendations
        }
    
    def _generate_hipaa_report(
        self,
        db: Session,
        period_start: datetime,
        period_end: datetime
    ) -> Dict[str, Any]:
        """HIPAA 준수 리포트 생성 (기본 구조)"""
        
        # 기본 구조만 제공 (실제 의료 데이터가 없으므로)
        return {
            'summary': {
                'total_events': 0,
                'compliant_events': 0,
                'non_compliant_events': 0,
                'compliance_score': 100
            },
            'details': {},
            'findings': [],
            'recommendations': ['HIPAA 관련 데이터가 없습니다']
        }
    
    def _generate_pci_dss_report(
        self,
        db: Session,
        period_start: datetime,
        period_end: datetime
    ) -> Dict[str, Any]:
        """PCI DSS 준수 리포트 생성 (기본 구조)"""
        
        return {
            'summary': {
                'total_events': 0,
                'compliant_events': 0,
                'non_compliant_events': 0,
                'compliance_score': 100
            },
            'details': {},
            'findings': [],
            'recommendations': ['PCI DSS 관련 데이터가 없습니다']
        }
    
    def _save_report_file(self, report_id: str, report_type: str, report_data: Dict[str, Any]) -> str:
        """리포트 파일 저장"""
        
        # 리포트 디렉토리 생성
        reports_dir = Path("data/reports")
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        # 파일 경로 생성
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{report_type}_{timestamp}_{report_id}.json"
        file_path = reports_dir / filename
        
        # JSON 파일로 저장
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2, default=str)
        
        return str(file_path)


# 전역 규정 준수 서비스 인스턴스
compliance_service = ComplianceService()
