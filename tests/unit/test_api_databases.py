"""
데이터베이스 API 엔드포인트 단위 테스트
"""

import pytest
import json
from unittest.mock import patch, Mock

from app.database import Database


@pytest.mark.unit
class TestDatabasesAPI:
    """데이터베이스 API 테스트"""
    
    def test_get_databases_empty(self, client, test_db):
        """빈 데이터베이스 목록 조회 테스트"""
        response = client.get("/api/databases")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_get_databases_with_data(self, client, test_db, database_factory):
        """데이터베이스 목록 조회 테스트"""
        # 테스트 데이터 생성
        db1 = database_factory.create(test_db, name="db1", display_name="데이터베이스 1")
        db2 = database_factory.create(test_db, name="db2", display_name="데이터베이스 2")
        
        response = client.get("/api/databases")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        
        # 데이터 검증
        db_names = [db["name"] for db in data]
        assert "db1" in db_names
        assert "db2" in db_names
    
    def test_get_database_by_id(self, client, test_db, database_factory):
        """특정 데이터베이스 조회 테스트"""
        database = database_factory.create(test_db, name="test_db")
        
        response = client.get(f"/api/databases/{database.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == database.id
        assert data["name"] == "test_db"
        assert data["display_name"] == "테스트 데이터베이스"
    
    def test_get_database_not_found(self, client, test_db):
        """존재하지 않는 데이터베이스 조회 테스트"""
        response = client.get("/api/databases/nonexistent-id")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
    
    def test_create_database(self, client, test_db):
        """데이터베이스 생성 테스트"""
        database_data = {
            "name": "new_db",
            "display_name": "새 데이터베이스",
            "host": "localhost",
            "port": 5432,
            "database_name": "newdb",
            "username": "user",
            "password_encrypted": "password",
            "ssl_mode": "require",
            "environment": "development",
            "priority": "medium"
        }
        
        response = client.post("/api/databases", json=database_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "new_db"
        assert data["display_name"] == "새 데이터베이스"
        assert data["host"] == "localhost"
        assert data["is_active"] is True
        
        # 데이터베이스에 실제로 저장되었는지 확인
        created_db = test_db.query(Database).filter(Database.name == "new_db").first()
        assert created_db is not None
    
    def test_create_database_duplicate_name(self, client, test_db, database_factory):
        """중복 이름으로 데이터베이스 생성 테스트"""
        database_factory.create(test_db, name="duplicate_db")
        
        database_data = {
            "name": "duplicate_db",
            "display_name": "중복 데이터베이스",
            "host": "localhost",
            "port": 5432,
            "database_name": "dupdb",
            "username": "user",
            "password_encrypted": "password",
            "environment": "development",
            "priority": "medium"
        }
        
        response = client.post("/api/databases", json=database_data)
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
    
    def test_create_database_invalid_data(self, client, test_db):
        """잘못된 데이터로 데이터베이스 생성 테스트"""
        invalid_data = {
            "name": "",  # 빈 이름
            "host": "localhost"
            # 필수 필드 누락
        }
        
        response = client.post("/api/databases", json=invalid_data)
        
        assert response.status_code == 422  # Validation error
    
    def test_update_database(self, client, test_db, database_factory):
        """데이터베이스 수정 테스트"""
        database = database_factory.create(test_db, name="update_test")
        
        update_data = {
            "display_name": "수정된 데이터베이스",
            "host": "updated-host",
            "port": 5433,
            "priority": "high"
        }
        
        response = client.put(f"/api/databases/{database.id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "수정된 데이터베이스"
        assert data["host"] == "updated-host"
        assert data["port"] == 5433
        assert data["priority"] == "high"
        
        # 데이터베이스에 실제로 업데이트되었는지 확인
        test_db.refresh(database)
        assert database.display_name == "수정된 데이터베이스"
        assert database.host == "updated-host"
    
    def test_update_database_not_found(self, client, test_db):
        """존재하지 않는 데이터베이스 수정 테스트"""
        update_data = {"display_name": "수정된 이름"}
        
        response = client.put("/api/databases/nonexistent-id", json=update_data)
        
        assert response.status_code == 404
    
    def test_delete_database(self, client, test_db, database_factory):
        """데이터베이스 삭제 테스트"""
        database = database_factory.create(test_db, name="delete_test")
        
        response = client.delete(f"/api/databases/{database.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        
        # 소프트 삭제 확인 (is_active = False)
        test_db.refresh(database)
        assert database.is_active is False
    
    def test_delete_database_not_found(self, client, test_db):
        """존재하지 않는 데이터베이스 삭제 테스트"""
        response = client.delete("/api/databases/nonexistent-id")
        
        assert response.status_code == 404
    
    @patch('app.core.database_manager.db_manager.test_connection')
    def test_test_database_connection_success(self, mock_test_connection, client, test_db, database_factory):
        """데이터베이스 연결 테스트 성공"""
        mock_test_connection.return_value = {
            "success": True,
            "message": "연결 성공",
            "response_time": 0.1
        }
        
        database = database_factory.create(test_db, name="connection_test")
        
        response = client.post(f"/api/databases/{database.id}/test-connection")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "연결 성공"
        assert "response_time" in data
        
        # 연결 상태가 업데이트되었는지 확인
        test_db.refresh(database)
        assert database.connection_status == "connected"
        assert database.last_connection_test is not None
    
    @patch('app.core.database_manager.db_manager.test_connection')
    def test_test_database_connection_failure(self, mock_test_connection, client, test_db, database_factory):
        """데이터베이스 연결 테스트 실패"""
        mock_test_connection.return_value = {
            "success": False,
            "message": "연결 실패: 호스트에 연결할 수 없습니다",
            "error": "Connection refused"
        }
        
        database = database_factory.create(test_db, name="connection_fail_test")
        
        response = client.post(f"/api/databases/{database.id}/test-connection")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "연결 실패" in data["message"]
        
        # 연결 상태가 업데이트되었는지 확인
        test_db.refresh(database)
        assert database.connection_status == "error"
    
    def test_get_database_backups(self, client, test_db, database_factory, backup_factory):
        """데이터베이스 백업 목록 조회 테스트"""
        database = database_factory.create(test_db, name="backup_test")
        
        # 테스트 백업 생성
        backup1 = backup_factory.create(test_db, database_id=database.id, backup_type="full")
        backup2 = backup_factory.create(test_db, database_id=database.id, backup_type="incremental")
        
        response = client.get(f"/api/databases/{database.id}/backups")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        
        backup_types = [backup["backup_type"] for backup in data]
        assert "full" in backup_types
        assert "incremental" in backup_types
    
    def test_get_database_backups_empty(self, client, test_db, database_factory):
        """백업이 없는 데이터베이스의 백업 목록 조회 테스트"""
        database = database_factory.create(test_db, name="no_backup_test")
        
        response = client.get(f"/api/databases/{database.id}/backups")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0
    
    def test_get_database_statistics(self, client, test_db, database_factory, backup_factory):
        """데이터베이스 통계 조회 테스트"""
        database = database_factory.create(test_db, name="stats_test")
        
        # 다양한 상태의 백업 생성
        backup_factory.create(test_db, database_id=database.id, status="completed")
        backup_factory.create(test_db, database_id=database.id, status="completed")
        backup_factory.create(test_db, database_id=database.id, status="failed")
        
        response = client.get(f"/api/databases/{database.id}/statistics")
        
        assert response.status_code == 200
        data = response.json()
        assert "total_backups" in data
        assert "successful_backups" in data
        assert "failed_backups" in data
        assert data["total_backups"] == 3
        assert data["successful_backups"] == 2
        assert data["failed_backups"] == 1
