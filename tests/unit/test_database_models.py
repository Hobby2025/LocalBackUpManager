"""
데이터베이스 모델 단위 테스트
"""

import pytest
from datetime import datetime
from sqlalchemy.exc import IntegrityError

from app.database import (
    User, Database, Backup, BackupConfig, Schedule, 
    Notification, SystemLog, AuditLog, AccessLog, 
    SecurityEvent, ComplianceReport
)


@pytest.mark.unit
class TestUserModel:
    """사용자 모델 테스트"""
    
    def test_create_user(self, test_db, user_factory):
        """사용자 생성 테스트"""
        user = user_factory.create(test_db, username="testuser")
        
        assert user.id is not None
        assert user.username == "testuser"
        assert user.full_name == "테스트 사용자"
        assert user.role == "admin"
        assert user.is_active is True
        assert user.created_at is not None
        assert user.updated_at is not None
    
    def test_user_unique_username(self, test_db, user_factory):
        """사용자명 유니크 제약 테스트"""
        user_factory.create(test_db, username="duplicate")
        
        with pytest.raises(IntegrityError):
            user_factory.create(test_db, username="duplicate")
    
    def test_user_required_fields(self, test_db):
        """필수 필드 검증 테스트"""
        with pytest.raises(IntegrityError):
            user = User(password_hash="hash", password_salt="salt")
            test_db.add(user)
            test_db.commit()


@pytest.mark.unit
class TestDatabaseModel:
    """데이터베이스 모델 테스트"""
    
    def test_create_database(self, test_db, database_factory):
        """데이터베이스 생성 테스트"""
        database = database_factory.create(test_db, name="test_db")
        
        assert database.id is not None
        assert database.name == "test_db"
        assert database.display_name == "테스트 데이터베이스"
        assert database.host == "localhost"
        assert database.port == 5432
        assert database.environment == "development"
        assert database.priority == "medium"
        assert database.is_active is True
        assert database.connection_status == "unknown"
    
    def test_database_unique_name(self, test_db, database_factory):
        """데이터베이스명 유니크 제약 테스트"""
        database_factory.create(test_db, name="duplicate_db")
        
        with pytest.raises(IntegrityError):
            database_factory.create(test_db, name="duplicate_db")
    
    def test_database_default_values(self, test_db):
        """기본값 테스트"""
        database = Database(
            name="test_default",
            display_name="테스트",
            host="localhost",
            database_name="testdb",
            username="user",
            password_encrypted="pass",
            environment="development",
            priority="medium"
        )
        test_db.add(database)
        test_db.commit()
        test_db.refresh(database)
        
        assert database.port == 5432
        assert database.ssl_mode == "require"
        assert database.is_active is True
        assert database.connection_status == "unknown"


@pytest.mark.unit
class TestBackupModel:
    """백업 모델 테스트"""
    
    def test_create_backup(self, test_db, backup_factory):
        """백업 생성 테스트"""
        backup = backup_factory.create(test_db, database_id="test-db-id")
        
        assert backup.id is not None
        assert backup.database_id == "test-db-id"
        assert backup.backup_type == "full"
        assert backup.status == "completed"
        assert backup.file_size == 1024
        assert backup.compressed_size == 512
        assert backup.compression_ratio == 0.5
        assert backup.is_encrypted is True
        assert backup.checksum == "abc123def456"
    
    def test_backup_required_fields(self, test_db):
        """필수 필드 검증 테스트"""
        with pytest.raises(IntegrityError):
            backup = Backup()
            test_db.add(backup)
            test_db.commit()
    
    def test_backup_status_values(self, test_db):
        """백업 상태값 테스트"""
        valid_statuses = ["pending", "running", "completed", "failed", "cancelled"]
        
        for status in valid_statuses:
            backup = Backup(
                database_id="test-db",
                backup_type="full",
                status=status
            )
            test_db.add(backup)
            test_db.commit()
            test_db.delete(backup)
            test_db.commit()


@pytest.mark.unit
class TestAuditLogModel:
    """감사 로그 모델 테스트"""
    
    def test_create_audit_log(self, test_db):
        """감사 로그 생성 테스트"""
        audit_log = AuditLog(
            user_id="test-user",
            username="testuser",
            action="CREATE",
            resource_type="database",
            ip_address="127.0.0.1",
            status="SUCCESS"
        )
        test_db.add(audit_log)
        test_db.commit()
        test_db.refresh(audit_log)
        
        assert audit_log.id is not None
        assert audit_log.user_id == "test-user"
        assert audit_log.username == "testuser"
        assert audit_log.action == "CREATE"
        assert audit_log.resource_type == "database"
        assert audit_log.ip_address == "127.0.0.1"
        assert audit_log.status == "SUCCESS"
        assert audit_log.created_at is not None
    
    def test_audit_log_with_values(self, test_db):
        """변경값이 포함된 감사 로그 테스트"""
        old_values = {"name": "old_name", "status": "inactive"}
        new_values = {"name": "new_name", "status": "active"}
        compliance_tags = {"tags": ["GDPR"], "gdpr_relevant": True}
        
        audit_log = AuditLog(
            user_id="test-user",
            username="testuser",
            action="UPDATE",
            resource_type="database",
            resource_id="db-123",
            old_values=old_values,
            new_values=new_values,
            ip_address="192.168.1.1",
            status="SUCCESS",
            compliance_tags=compliance_tags
        )
        test_db.add(audit_log)
        test_db.commit()
        test_db.refresh(audit_log)
        
        assert audit_log.old_values == old_values
        assert audit_log.new_values == new_values
        assert audit_log.compliance_tags == compliance_tags


@pytest.mark.unit
class TestAccessLogModel:
    """접근 로그 모델 테스트"""
    
    def test_create_access_log(self, test_db):
        """접근 로그 생성 테스트"""
        access_log = AccessLog(
            method="GET",
            endpoint="/api/databases",
            path="/api/databases",
            response_status=200,
            ip_address="127.0.0.1",
            is_authenticated=True,
            risk_score=10
        )
        test_db.add(access_log)
        test_db.commit()
        test_db.refresh(access_log)
        
        assert access_log.id is not None
        assert access_log.method == "GET"
        assert access_log.endpoint == "/api/databases"
        assert access_log.response_status == 200
        assert access_log.ip_address == "127.0.0.1"
        assert access_log.is_authenticated is True
        assert access_log.risk_score == 10
        assert access_log.blocked is False
    
    def test_access_log_with_query_params(self, test_db):
        """쿼리 파라미터가 포함된 접근 로그 테스트"""
        query_params = {"limit": 10, "offset": 0, "filter": "active"}
        
        access_log = AccessLog(
            method="GET",
            endpoint="/api/databases",
            path="/api/databases",
            query_params=query_params,
            response_status=200,
            ip_address="127.0.0.1",
            risk_score=5
        )
        test_db.add(access_log)
        test_db.commit()
        test_db.refresh(access_log)
        
        assert access_log.query_params == query_params


@pytest.mark.unit
class TestSecurityEventModel:
    """보안 이벤트 모델 테스트"""
    
    def test_create_security_event(self, test_db):
        """보안 이벤트 생성 테스트"""
        security_event = SecurityEvent(
            event_type="AUTHENTICATION_FAILED",
            severity="MEDIUM",
            ip_address="192.168.1.100",
            description="로그인 실패"
        )
        test_db.add(security_event)
        test_db.commit()
        test_db.refresh(security_event)
        
        assert security_event.id is not None
        assert security_event.event_type == "AUTHENTICATION_FAILED"
        assert security_event.severity == "MEDIUM"
        assert security_event.ip_address == "192.168.1.100"
        assert security_event.description == "로그인 실패"
        assert security_event.resolved is False
        assert security_event.auto_blocked is False
    
    def test_security_event_with_details(self, test_db):
        """상세 정보가 포함된 보안 이벤트 테스트"""
        details = {
            "failed_attempts": 5,
            "user_agent": "Mozilla/5.0",
            "attempted_username": "admin"
        }
        
        security_event = SecurityEvent(
            event_type="BRUTE_FORCE_ATTACK",
            severity="CRITICAL",
            ip_address="10.0.0.1",
            description="브루트 포스 공격 감지",
            details=details,
            auto_blocked=True
        )
        test_db.add(security_event)
        test_db.commit()
        test_db.refresh(security_event)
        
        assert security_event.details == details
        assert security_event.auto_blocked is True


@pytest.mark.unit
class TestComplianceReportModel:
    """규정 준수 리포트 모델 테스트"""
    
    def test_create_compliance_report(self, test_db):
        """규정 준수 리포트 생성 테스트"""
        report = ComplianceReport(
            report_type="GDPR",
            period_start=datetime(2024, 1, 1),
            period_end=datetime(2024, 1, 31),
            generated_by="admin",
            status="COMPLETED"
        )
        test_db.add(report)
        test_db.commit()
        test_db.refresh(report)
        
        assert report.id is not None
        assert report.report_type == "GDPR"
        assert report.status == "COMPLETED"
        assert report.total_events == 0
        assert report.compliant_events == 0
        assert report.non_compliant_events == 0
    
    def test_compliance_report_with_results(self, test_db):
        """결과가 포함된 규정 준수 리포트 테스트"""
        findings = [
            {"type": "WARNING", "message": "테스트 발견사항"}
        ]
        recommendations = [
            "정기적인 감사 수행",
            "접근 권한 검토"
        ]
        
        report = ComplianceReport(
            report_type="SOX",
            period_start=datetime(2024, 1, 1),
            period_end=datetime(2024, 1, 31),
            generated_by="admin",
            status="COMPLETED",
            total_events=100,
            compliant_events=95,
            non_compliant_events=5,
            compliance_score=95.0,
            findings=findings,
            recommendations=recommendations
        )
        test_db.add(report)
        test_db.commit()
        test_db.refresh(report)
        
        assert report.total_events == 100
        assert report.compliance_score == 95.0
        assert report.findings == findings
        assert report.recommendations == recommendations


@pytest.mark.unit
class TestSystemLogModel:
    """시스템 로그 모델 테스트"""
    
    def test_create_system_log(self, test_db):
        """시스템 로그 생성 테스트"""
        system_log = SystemLog(
            level="INFO",
            component="backup_engine",
            message="백업 시작"
        )
        test_db.add(system_log)
        test_db.commit()
        test_db.refresh(system_log)
        
        assert system_log.id is not None
        assert system_log.level == "INFO"
        assert system_log.component == "backup_engine"
        assert system_log.message == "백업 시작"
        assert system_log.created_at is not None
    
    def test_system_log_with_details(self, test_db):
        """상세 정보가 포함된 시스템 로그 테스트"""
        details = {
            "database_id": "db-123",
            "backup_type": "full",
            "file_size": 1024
        }
        
        system_log = SystemLog(
            level="INFO",
            component="backup_engine",
            message="백업 완료",
            details=details,
            database_id="db-123",
            ip_address="127.0.0.1"
        )
        test_db.add(system_log)
        test_db.commit()
        test_db.refresh(system_log)
        
        assert system_log.details == details
        assert system_log.database_id == "db-123"
        assert system_log.ip_address == "127.0.0.1"
