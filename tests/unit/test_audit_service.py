"""
감사 서비스 단위 테스트
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from fastapi import Request

from app.core.audit_service import audit_service, AuditService
from app.database import AuditLog, AccessLog, SecurityEvent


@pytest.mark.unit
class TestAuditService:
    """감사 서비스 테스트"""
    
    def test_audit_service_initialization(self):
        """감사 서비스 초기화 테스트"""
        service = AuditService()
        assert service is not None
        assert hasattr(service, 'risk_thresholds')
        assert 'failed_login_attempts' in service.risk_thresholds
        assert 'suspicious_ip_score' in service.risk_thresholds
    
    def test_log_audit_event_basic(self, test_db):
        """기본 감사 이벤트 로깅 테스트"""
        audit_log = audit_service.log_audit_event(
            db=test_db,
            user_id="test-user",
            username="testuser",
            action="CREATE",
            resource_type="database",
            resource_id="db-123",
            resource_name="테스트 DB",
            ip_address="127.0.0.1",
            status="SUCCESS"
        )
        
        assert audit_log.id is not None
        assert audit_log.user_id == "test-user"
        assert audit_log.username == "testuser"
        assert audit_log.action == "CREATE"
        assert audit_log.resource_type == "database"
        assert audit_log.resource_id == "db-123"
        assert audit_log.resource_name == "테스트 DB"
        assert audit_log.ip_address == "127.0.0.1"
        assert audit_log.status == "SUCCESS"
        assert audit_log.created_at is not None
    
    def test_log_audit_event_with_values(self, test_db):
        """변경값이 포함된 감사 이벤트 로깅 테스트"""
        old_values = {"name": "old_name", "status": "inactive"}
        new_values = {"name": "new_name", "status": "active"}
        compliance_tags = ["GDPR", "SOX"]
        
        audit_log = audit_service.log_audit_event(
            db=test_db,
            user_id="test-user",
            username="testuser",
            action="UPDATE",
            resource_type="database",
            old_values=old_values,
            new_values=new_values,
            ip_address="192.168.1.1",
            compliance_tags=compliance_tags,
            duration_ms=150
        )
        
        assert audit_log.old_values == old_values
        assert audit_log.new_values == new_values
        assert audit_log.duration_ms == 150
        assert audit_log.compliance_tags["tags"] == compliance_tags
        assert audit_log.compliance_tags["gdpr_relevant"] is True
        assert audit_log.compliance_tags["sox_relevant"] is True
    
    def test_log_audit_event_high_privilege_action(self, test_db):
        """고권한 작업 감사 이벤트 로깅 테스트"""
        with patch.object(audit_service, 'log_security_event') as mock_security_log:
            audit_log = audit_service.log_audit_event(
                db=test_db,
                user_id="test-user",
                username="testuser",
                action="DELETE",  # 고권한 작업
                resource_type="backup",
                ip_address="127.0.0.1"
            )
            
            # 보안 이벤트도 함께 생성되었는지 확인
            mock_security_log.assert_called_once()
            call_args = mock_security_log.call_args
            assert call_args[1]['event_type'] == 'HIGH_PRIVILEGE_ACTION'
            assert call_args[1]['severity'] == 'MEDIUM'
    
    def test_log_access_basic(self, test_db):
        """기본 접근 로그 테스트"""
        # Mock Request 객체 생성
        mock_request = Mock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/api/databases"
        mock_request.query_params = {}
        mock_request.headers = {"user-agent": "test-browser"}
        mock_request.cookies = {}
        mock_request.client.host = "127.0.0.1"
        
        access_log = audit_service.log_access(
            db=test_db,
            request=mock_request,
            response_status=200,
            response_size=1024,
            response_time_ms=50,
            user_id="test-user",
            username="testuser",
            is_authenticated=True,
            auth_method="session"
        )
        
        assert access_log.id is not None
        assert access_log.method == "GET"
        assert access_log.endpoint == "/api/databases"
        assert access_log.response_status == 200
        assert access_log.response_size == 1024
        assert access_log.response_time_ms == 50
        assert access_log.user_id == "test-user"
        assert access_log.username == "testuser"
        assert access_log.is_authenticated is True
        assert access_log.auth_method == "session"
        assert access_log.risk_score >= 0
    
    def test_log_access_high_risk(self, test_db):
        """높은 위험도 접근 로그 테스트"""
        mock_request = Mock(spec=Request)
        mock_request.method = "DELETE"
        mock_request.url.path = "/api/databases/123"
        mock_request.query_params = {}
        mock_request.headers = {"user-agent": "suspicious-bot"}
        mock_request.cookies = {}
        mock_request.client.host = "192.168.1.100"
        
        with patch.object(audit_service, 'log_security_event') as mock_security_log:
            with patch.object(audit_service, '_calculate_risk_score', return_value=85):
                access_log = audit_service.log_access(
                    db=test_db,
                    request=mock_request,
                    response_status=200
                )
                
                assert access_log.risk_score == 85
                # 높은 위험도로 인한 보안 이벤트 생성 확인
                mock_security_log.assert_called_once()
                call_args = mock_security_log.call_args
                assert call_args[1]['event_type'] == 'HIGH_RISK_ACCESS'
    
    def test_log_security_event(self, test_db):
        """보안 이벤트 로깅 테스트"""
        details = {"failed_attempts": 5, "user_agent": "test-browser"}
        
        security_event = audit_service.log_security_event(
            db=test_db,
            event_type="BRUTE_FORCE_ATTACK",
            severity="CRITICAL",
            ip_address="192.168.1.100",
            description="브루트 포스 공격 감지",
            user_id="test-user",
            username="testuser",
            details=details,
            auto_blocked=True
        )
        
        assert security_event.id is not None
        assert security_event.event_type == "BRUTE_FORCE_ATTACK"
        assert security_event.severity == "CRITICAL"
        assert security_event.ip_address == "192.168.1.100"
        assert security_event.description == "브루트 포스 공격 감지"
        assert security_event.user_id == "test-user"
        assert security_event.username == "testuser"
        assert security_event.details == details
        assert security_event.auto_blocked is True
        assert security_event.resolved is False
    
    def test_get_audit_logs_filtering(self, test_db):
        """감사 로그 필터링 조회 테스트"""
        # 테스트 데이터 생성
        audit_service.log_audit_event(
            db=test_db,
            user_id="user1",
            username="user1",
            action="CREATE",
            resource_type="database",
            ip_address="127.0.0.1"
        )
        audit_service.log_audit_event(
            db=test_db,
            user_id="user2",
            username="user2",
            action="UPDATE",
            resource_type="backup",
            ip_address="127.0.0.1"
        )
        audit_service.log_audit_event(
            db=test_db,
            user_id="user1",
            username="user1",
            action="DELETE",
            resource_type="database",
            ip_address="127.0.0.1"
        )
        
        # 사용자별 필터링
        user1_logs = audit_service.get_audit_logs(db=test_db, user_id="user1")
        assert len(user1_logs) == 2
        assert all(log.user_id == "user1" for log in user1_logs)
        
        # 액션별 필터링
        create_logs = audit_service.get_audit_logs(db=test_db, action="CREATE")
        assert len(create_logs) == 1
        assert create_logs[0].action == "CREATE"
        
        # 리소스 타입별 필터링
        db_logs = audit_service.get_audit_logs(db=test_db, resource_type="database")
        assert len(db_logs) == 2
        assert all(log.resource_type == "database" for log in db_logs)
    
    def test_get_audit_logs_date_filtering(self, test_db):
        """감사 로그 날짜 필터링 테스트"""
        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)
        tomorrow = now + timedelta(days=1)
        
        # 테스트 데이터 생성
        audit_service.log_audit_event(
            db=test_db,
            user_id="test-user",
            username="testuser",
            action="CREATE",
            resource_type="database",
            ip_address="127.0.0.1"
        )
        
        # 날짜 범위 필터링
        logs_in_range = audit_service.get_audit_logs(
            db=test_db,
            start_date=yesterday,
            end_date=tomorrow
        )
        assert len(logs_in_range) == 1
        
        # 범위 밖 필터링
        logs_out_range = audit_service.get_audit_logs(
            db=test_db,
            start_date=tomorrow,
            end_date=tomorrow + timedelta(days=1)
        )
        assert len(logs_out_range) == 0
    
    def test_get_access_logs_filtering(self, test_db):
        """접근 로그 필터링 조회 테스트"""
        mock_request1 = Mock(spec=Request)
        mock_request1.method = "GET"
        mock_request1.url.path = "/api/databases"
        mock_request1.query_params = {}
        mock_request1.headers = {}
        mock_request1.cookies = {}
        mock_request1.client.host = "127.0.0.1"
        
        mock_request2 = Mock(spec=Request)
        mock_request2.method = "POST"
        mock_request2.url.path = "/api/backups"
        mock_request2.query_params = {}
        mock_request2.headers = {}
        mock_request2.cookies = {}
        mock_request2.client.host = "192.168.1.1"
        
        # 테스트 데이터 생성
        audit_service.log_access(db=test_db, request=mock_request1, response_status=200)
        audit_service.log_access(db=test_db, request=mock_request2, response_status=201)
        
        # IP별 필터링
        ip1_logs = audit_service.get_access_logs(db=test_db, ip_address="127.0.0.1")
        assert len(ip1_logs) == 1
        assert ip1_logs[0].ip_address == "127.0.0.1"
        
        # 엔드포인트별 필터링
        db_logs = audit_service.get_access_logs(db=test_db, endpoint="databases")
        assert len(db_logs) == 1
        assert "databases" in db_logs[0].endpoint
    
    def test_resolve_security_event(self, test_db):
        """보안 이벤트 해결 처리 테스트"""
        # 보안 이벤트 생성
        security_event = audit_service.log_security_event(
            db=test_db,
            event_type="SUSPICIOUS_ACTIVITY",
            severity="MEDIUM",
            ip_address="192.168.1.1",
            description="의심스러운 활동"
        )
        
        # 해결 처리
        resolved_event = audit_service.resolve_security_event(
            db=test_db,
            event_id=security_event.id,
            resolved_by="admin",
            resolution_notes="조사 완료, 정상 활동으로 확인"
        )
        
        assert resolved_event is not None
        assert resolved_event.resolved is True
        assert resolved_event.resolved_by == "admin"
        assert resolved_event.resolution_notes == "조사 완료, 정상 활동으로 확인"
        assert resolved_event.resolved_at is not None
    
    def test_get_audit_statistics(self, test_db):
        """감사 통계 조회 테스트"""
        # 테스트 데이터 생성
        audit_service.log_audit_event(
            db=test_db,
            user_id="user1",
            username="user1",
            action="CREATE",
            resource_type="database",
            ip_address="127.0.0.1",
            status="SUCCESS"
        )
        audit_service.log_audit_event(
            db=test_db,
            user_id="user2",
            username="user2",
            action="UPDATE",
            resource_type="backup",
            ip_address="192.168.1.1",
            status="FAILED"
        )
        
        mock_request = Mock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/api/test"
        mock_request.query_params = {}
        mock_request.headers = {}
        mock_request.cookies = {}
        mock_request.client.host = "127.0.0.1"
        
        audit_service.log_access(db=test_db, request=mock_request, response_status=200)
        
        audit_service.log_security_event(
            db=test_db,
            event_type="TEST_EVENT",
            severity="LOW",
            ip_address="127.0.0.1",
            description="테스트 이벤트"
        )
        
        # 통계 조회
        stats = audit_service.get_audit_statistics(db=test_db)
        
        assert "period" in stats
        assert "totals" in stats
        assert stats["totals"]["audit_logs"] == 2
        assert stats["totals"]["access_logs"] == 1
        assert stats["totals"]["security_events"] == 1
        
        assert "action_statistics" in stats
        assert "user_statistics" in stats
        assert "ip_statistics" in stats
    
    def test_calculate_risk_score(self):
        """위험도 점수 계산 테스트"""
        service = AuditService()
        
        # 내부 IP (낮은 위험도)
        score1 = service._calculate_risk_score("192.168.1.1", "/api/databases", "GET")
        assert score1 >= 0
        assert score1 <= 50  # 내부 IP는 상대적으로 낮은 점수
        
        # 외부 IP + 위험한 경로 + 위험한 메서드
        score2 = service._calculate_risk_score("8.8.8.8", "/api/users", "DELETE")
        assert score2 > score1
        assert score2 <= 100
        
        # 로컬호스트 (가장 안전)
        score3 = service._calculate_risk_score("127.0.0.1", "/api/health", "GET")
        assert score3 <= score1
    
    def test_extract_endpoint_pattern(self):
        """엔드포인트 패턴 추출 테스트"""
        service = AuditService()
        
        # UUID 패턴 치환
        path1 = "/api/databases/550e8400-e29b-41d4-a716-446655440000"
        pattern1 = service._extract_endpoint(path1)
        assert pattern1 == "/api/databases/{id}"
        
        # 숫자 ID 패턴 치환
        path2 = "/api/backups/123"
        pattern2 = service._extract_endpoint(path2)
        assert pattern2 == "/api/backups/{id}"
        
        # 일반 경로
        path3 = "/api/databases"
        pattern3 = service._extract_endpoint(path3)
        assert pattern3 == "/api/databases"
    
    def test_get_client_ip_extraction(self):
        """클라이언트 IP 추출 테스트"""
        service = AuditService()
        
        # X-Forwarded-For 헤더가 있는 경우
        mock_request1 = Mock(spec=Request)
        mock_request1.headers = {"x-forwarded-for": "203.0.113.1, 192.168.1.1"}
        mock_request1.client.host = "127.0.0.1"
        
        ip1 = service._get_client_ip(mock_request1)
        assert ip1 == "203.0.113.1"  # 첫 번째 IP 사용
        
        # X-Real-IP 헤더가 있는 경우
        mock_request2 = Mock(spec=Request)
        mock_request2.headers = {"x-real-ip": "203.0.113.2"}
        mock_request2.client.host = "127.0.0.1"
        
        ip2 = service._get_client_ip(mock_request2)
        assert ip2 == "203.0.113.2"
        
        # 직접 연결인 경우
        mock_request3 = Mock(spec=Request)
        mock_request3.headers = {}
        mock_request3.client.host = "192.168.1.100"
        
        ip3 = service._get_client_ip(mock_request3)
        assert ip3 == "192.168.1.100"
