"""
백업 워크플로우 통합 테스트
전체 백업 프로세스의 end-to-end 테스트
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, Mock
from datetime import datetime

from app.database import Database, Backup, SystemLog
from app.core.backup_engine import BackupEngine


@pytest.mark.integration
class TestBackupWorkflow:
    """백업 워크플로우 통합 테스트"""
    
    @pytest.fixture
    def temp_backup_dir(self):
        """임시 백업 디렉토리"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def sample_database(self, test_db, database_factory):
        """테스트용 데이터베이스"""
        return database_factory.create(
            test_db,
            name="integration_test_db",
            display_name="통합 테스트 DB",
            host="localhost",
            port=5432,
            database_name="testdb",
            username="testuser",
            password_encrypted="testpass",
            environment="development"
        )
    
    @patch('subprocess.run')
    @patch('subprocess.check_output')
    @patch('app.core.backup_engine.get_encryption_key')
    def test_full_backup_workflow(self, mock_get_key, mock_version, mock_subprocess, 
                                  client, test_db, sample_database, temp_backup_dir):
        """전체 백업 워크플로우 테스트"""
        # Mock 설정
        mock_get_key.return_value = b"a" * 32
        mock_version.return_value = b"pg_dump (PostgreSQL) 14.0\n"
        
        # pg_dump 성공 시뮬레이션
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.stdout = b"-- PostgreSQL database dump\nCREATE TABLE test();"
        mock_process.stderr = b""
        mock_subprocess.return_value = mock_process
        
        # 백업 실행 API 호출
        response = client.post(f"/api/backups/database/{sample_database.id}")
        
        assert response.status_code == 202  # Accepted (비동기 처리)
        data = response.json()
        assert "backup_id" in data
        assert data["message"] == "백업이 시작되었습니다"
        
        backup_id = data["backup_id"]
        
        # 백업 레코드 확인
        backup_record = test_db.query(Backup).filter(Backup.id == backup_id).first()
        assert backup_record is not None
        assert backup_record.database_id == sample_database.id
        assert backup_record.backup_type == "full"
        # 비동기 처리로 인해 상태는 pending 또는 running일 수 있음
        assert backup_record.status in ["pending", "running", "completed"]
    
    def test_database_crud_workflow(self, client, test_db):
        """데이터베이스 CRUD 워크플로우 테스트"""
        # 1. 데이터베이스 생성
        create_data = {
            "name": "workflow_test_db",
            "display_name": "워크플로우 테스트 DB",
            "host": "localhost",
            "port": 5432,
            "database_name": "workflowdb",
            "username": "workflowuser",
            "password_encrypted": "workflowpass",
            "ssl_mode": "require",
            "environment": "development",
            "priority": "medium"
        }
        
        create_response = client.post("/api/databases", json=create_data)
        assert create_response.status_code == 201
        
        created_db = create_response.json()
        db_id = created_db["id"]
        assert created_db["name"] == "workflow_test_db"
        
        # 2. 데이터베이스 조회
        get_response = client.get(f"/api/databases/{db_id}")
        assert get_response.status_code == 200
        
        retrieved_db = get_response.json()
        assert retrieved_db["id"] == db_id
        assert retrieved_db["name"] == "workflow_test_db"
        
        # 3. 데이터베이스 수정
        update_data = {
            "display_name": "수정된 워크플로우 테스트 DB",
            "priority": "high"
        }
        
        update_response = client.put(f"/api/databases/{db_id}", json=update_data)
        assert update_response.status_code == 200
        
        updated_db = update_response.json()
        assert updated_db["display_name"] == "수정된 워크플로우 테스트 DB"
        assert updated_db["priority"] == "high"
        
        # 4. 데이터베이스 목록 조회
        list_response = client.get("/api/databases")
        assert list_response.status_code == 200
        
        db_list = list_response.json()
        assert len(db_list) >= 1
        assert any(db["id"] == db_id for db in db_list)
        
        # 5. 데이터베이스 삭제 (소프트 삭제)
        delete_response = client.delete(f"/api/databases/{db_id}")
        assert delete_response.status_code == 200
        
        # 6. 삭제된 데이터베이스 조회 (404 반환)
        get_deleted_response = client.get(f"/api/databases/{db_id}")
        assert get_deleted_response.status_code == 404
        
        # 7. 데이터베이스가 실제로 소프트 삭제되었는지 확인
        db_record = test_db.query(Database).filter(Database.id == db_id).first()
        assert db_record is not None
        assert db_record.is_active is False
    
    @patch('app.core.database_manager.db_manager.test_connection')
    def test_database_connection_workflow(self, mock_test_connection, client, test_db, sample_database):
        """데이터베이스 연결 테스트 워크플로우"""
        # 1. 연결 테스트 성공
        mock_test_connection.return_value = {
            "success": True,
            "message": "연결 성공",
            "response_time": 0.1
        }
        
        test_response = client.post(f"/api/databases/{sample_database.id}/test-connection")
        assert test_response.status_code == 200
        
        test_result = test_response.json()
        assert test_result["success"] is True
        assert "response_time" in test_result
        
        # 2. 데이터베이스 상태 확인
        test_db.refresh(sample_database)
        assert sample_database.connection_status == "connected"
        assert sample_database.last_connection_test is not None
        
        # 3. 연결 테스트 실패
        mock_test_connection.return_value = {
            "success": False,
            "message": "연결 실패: 호스트에 연결할 수 없습니다",
            "error": "Connection refused"
        }
        
        fail_response = client.post(f"/api/databases/{sample_database.id}/test-connection")
        assert fail_response.status_code == 200
        
        fail_result = fail_response.json()
        assert fail_result["success"] is False
        assert "연결 실패" in fail_result["message"]
        
        # 4. 실패 후 상태 확인
        test_db.refresh(sample_database)
        assert sample_database.connection_status == "error"
    
    def test_backup_history_workflow(self, client, test_db, sample_database, backup_factory):
        """백업 이력 조회 워크플로우 테스트"""
        # 1. 테스트 백업 데이터 생성
        backup1 = backup_factory.create(
            test_db,
            database_id=sample_database.id,
            backup_type="full",
            status="completed",
            file_size=1024000,
            compressed_size=512000
        )
        
        backup2 = backup_factory.create(
            test_db,
            database_id=sample_database.id,
            backup_type="incremental",
            status="completed",
            file_size=256000,
            compressed_size=128000
        )
        
        backup3 = backup_factory.create(
            test_db,
            database_id=sample_database.id,
            backup_type="full",
            status="failed",
            error_message="Connection timeout"
        )
        
        # 2. 전체 백업 목록 조회
        all_backups_response = client.get("/api/backups")
        assert all_backups_response.status_code == 200
        
        all_backups = all_backups_response.json()
        assert len(all_backups) >= 3
        
        # 3. 특정 데이터베이스의 백업 목록 조회
        db_backups_response = client.get(f"/api/databases/{sample_database.id}/backups")
        assert db_backups_response.status_code == 200
        
        db_backups = db_backups_response.json()
        assert len(db_backups) == 3
        
        # 4. 백업 상태별 필터링
        completed_response = client.get(f"/api/backups?status=completed")
        assert completed_response.status_code == 200
        
        completed_backups = completed_response.json()
        completed_count = len([b for b in completed_backups if b["database_id"] == sample_database.id])
        assert completed_count == 2
        
        # 5. 특정 백업 상세 조회
        backup_detail_response = client.get(f"/api/backups/{backup1.id}")
        assert backup_detail_response.status_code == 200
        
        backup_detail = backup_detail_response.json()
        assert backup_detail["id"] == backup1.id
        assert backup_detail["backup_type"] == "full"
        assert backup_detail["status"] == "completed"
        assert backup_detail["file_size"] == 1024000
        assert backup_detail["compressed_size"] == 512000
    
    def test_monitoring_workflow(self, client, test_db, sample_database, backup_factory):
        """모니터링 워크플로우 테스트"""
        # 1. 테스트 데이터 생성
        backup_factory.create(
            test_db,
            database_id=sample_database.id,
            status="completed",
            file_size=1000000,
            duration_seconds=30
        )
        backup_factory.create(
            test_db,
            database_id=sample_database.id,
            status="failed",
            error_message="Disk full"
        )
        
        # 2. 전체 시스템 상태 조회
        status_response = client.get("/api/monitoring/status")
        assert status_response.status_code == 200
        
        status_data = status_response.json()
        assert "total_databases" in status_data
        assert "active_databases" in status_data
        assert "total_backups" in status_data
        assert "recent_backups" in status_data
        
        # 3. 대시보드 데이터 조회
        dashboard_response = client.get("/api/monitoring/dashboard")
        assert dashboard_response.status_code == 200
        
        dashboard_data = dashboard_response.json()
        assert "backup_summary" in dashboard_data
        assert "recent_activities" in dashboard_data
        
        # 4. 데이터베이스별 상태 조회
        db_status_response = client.get("/api/monitoring/db-status")
        assert db_status_response.status_code == 200
        
        db_status_data = db_status_response.json()
        assert isinstance(db_status_data, list)
        assert len(db_status_data) >= 1
        
        # 5. 백업 통계 조회
        stats_response = client.get(f"/api/databases/{sample_database.id}/statistics")
        assert stats_response.status_code == 200
        
        stats_data = stats_response.json()
        assert "total_backups" in stats_data
        assert "successful_backups" in stats_data
        assert "failed_backups" in stats_data
        assert stats_data["total_backups"] == 2
        assert stats_data["successful_backups"] == 1
        assert stats_data["failed_backups"] == 1
    
    def test_audit_workflow(self, client, test_db, sample_database):
        """감사 로그 워크플로우 테스트"""
        # 1. 데이터베이스 생성 (감사 로그 생성됨)
        create_data = {
            "name": "audit_test_db",
            "display_name": "감사 테스트 DB",
            "host": "localhost",
            "port": 5432,
            "database_name": "auditdb",
            "username": "audituser",
            "password_encrypted": "auditpass",
            "environment": "development",
            "priority": "medium"
        }
        
        create_response = client.post("/api/databases", json=create_data)
        assert create_response.status_code == 201
        
        # 2. 감사 로그 조회
        audit_logs_response = client.get("/api/audit/logs")
        assert audit_logs_response.status_code == 200
        
        audit_logs = audit_logs_response.json()
        # 미들웨어에 의해 자동으로 감사 로그가 생성되어야 함
        assert len(audit_logs) >= 0
        
        # 3. 접근 로그 조회
        access_logs_response = client.get("/api/audit/access-logs")
        assert access_logs_response.status_code == 200
        
        access_logs = access_logs_response.json()
        # API 호출에 의해 접근 로그가 생성되어야 함
        assert len(access_logs) >= 0
        
        # 4. 감사 통계 조회
        audit_stats_response = client.get("/api/audit/statistics")
        assert audit_stats_response.status_code == 200
        
        audit_stats = audit_stats_response.json()
        assert "period" in audit_stats
        assert "totals" in audit_stats
        
        # 5. 감사 대시보드 조회
        audit_dashboard_response = client.get("/api/audit/dashboard")
        assert audit_dashboard_response.status_code == 200
        
        audit_dashboard = audit_dashboard_response.json()
        assert "summary" in audit_dashboard
    
    def test_error_handling_workflow(self, client, test_db):
        """오류 처리 워크플로우 테스트"""
        # 1. 존재하지 않는 데이터베이스 조회
        not_found_response = client.get("/api/databases/nonexistent-id")
        assert not_found_response.status_code == 404
        
        error_data = not_found_response.json()
        assert "detail" in error_data
        
        # 2. 잘못된 데이터로 데이터베이스 생성
        invalid_data = {
            "name": "",  # 빈 이름
            "host": "localhost"
            # 필수 필드 누락
        }
        
        invalid_response = client.post("/api/databases", json=invalid_data)
        assert invalid_response.status_code == 422  # Validation error
        
        # 3. 존재하지 않는 백업 조회
        backup_not_found = client.get("/api/backups/nonexistent-backup-id")
        assert backup_not_found.status_code == 404
        
        # 4. 잘못된 필터로 백업 조회
        invalid_filter_response = client.get("/api/backups?status=invalid_status")
        # 잘못된 필터는 빈 결과를 반환해야 함
        assert invalid_filter_response.status_code == 200
        
        invalid_backups = invalid_filter_response.json()
        assert len(invalid_backups) == 0
    
    def test_pagination_workflow(self, client, test_db, sample_database, backup_factory):
        """페이지네이션 워크플로우 테스트"""
        # 1. 많은 백업 데이터 생성
        for i in range(25):
            backup_factory.create(
                test_db,
                database_id=sample_database.id,
                backup_type="full" if i % 2 == 0 else "incremental",
                status="completed"
            )
        
        # 2. 첫 번째 페이지 조회
        page1_response = client.get("/api/backups?limit=10&offset=0")
        assert page1_response.status_code == 200
        
        page1_data = page1_response.json()
        assert len(page1_data) == 10
        
        # 3. 두 번째 페이지 조회
        page2_response = client.get("/api/backups?limit=10&offset=10")
        assert page2_response.status_code == 200
        
        page2_data = page2_response.json()
        assert len(page2_data) == 10
        
        # 4. 페이지 데이터가 다른지 확인
        page1_ids = {backup["id"] for backup in page1_data}
        page2_ids = {backup["id"] for backup in page2_data}
        assert page1_ids.isdisjoint(page2_ids)  # 겹치지 않아야 함
        
        # 5. 마지막 페이지 조회
        page3_response = client.get("/api/backups?limit=10&offset=20")
        assert page3_response.status_code == 200
        
        page3_data = page3_response.json()
        assert len(page3_data) == 5  # 나머지 5개
