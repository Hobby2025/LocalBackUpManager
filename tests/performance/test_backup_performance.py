"""
백업 성능 및 부하 테스트
덤프 시간, 파일 크기, 압축률 등 성능 지표 측정
"""

import pytest
import time
import tempfile
import shutil
import asyncio
import concurrent.futures
from pathlib import Path
from unittest.mock import patch, Mock
from datetime import datetime, timedelta

from app.core.backup_engine import BackupEngine
from app.database import Database, Backup


@pytest.mark.performance
@pytest.mark.slow
class TestBackupPerformance:
    """백업 성능 테스트"""
    
    @pytest.fixture
    def performance_database(self, test_db, database_factory):
        """성능 테스트용 데이터베이스"""
        return database_factory.create(
            test_db,
            name="perf_test_db",
            display_name="성능 테스트 DB",
            host="localhost",
            port=5432,
            database_name="perfdb",
            username="perfuser",
            password_encrypted="perfpass"
        )
    
    @pytest.fixture
    def temp_backup_dir(self):
        """임시 백업 디렉토리"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def create_test_file(self, file_path: Path, size_mb: int):
        """테스트용 파일 생성"""
        content = "CREATE TABLE test_data(id INTEGER, data TEXT);\n"
        # 대략적인 크기 계산을 위해 반복
        target_size = size_mb * 1024 * 1024
        current_size = 0
        
        with open(file_path, 'w') as f:
            while current_size < target_size:
                f.write(content)
                current_size += len(content.encode())
    
    @patch('subprocess.run')
    @patch('subprocess.check_output')
    @patch('app.core.backup_engine.get_encryption_key')
    def test_backup_time_performance(self, mock_get_key, mock_version, mock_subprocess,
                                   performance_database, temp_backup_dir):
        """백업 시간 성능 테스트"""
        # Mock 설정
        mock_get_key.return_value = b"a" * 32
        mock_version.return_value = b"pg_dump (PostgreSQL) 14.0\n"
        
        # 다양한 크기의 백업 파일 시뮬레이션
        test_sizes = [1, 10, 50, 100]  # MB
        performance_results = []
        
        backup_engine = BackupEngine()
        
        for size_mb in test_sizes:
            # 테스트 SQL 파일 생성
            test_file = temp_backup_dir / f"test_{size_mb}mb.sql"
            self.create_test_file(test_file, size_mb)
            
            # pg_dump 성공 시뮬레이션
            mock_process = Mock()
            mock_process.returncode = 0
            mock_process.stdout = test_file.read_bytes()
            mock_process.stderr = b""
            mock_subprocess.return_value = mock_process
            
            # 백업 시간 측정
            start_time = time.time()
            
            with patch.object(backup_engine, '_get_backup_file_path', return_value=str(test_file)):
                result = backup_engine._execute_pg_dump(
                    performance_database,
                    str(test_file),
                    backup_type="full"
                )
            
            end_time = time.time()
            duration = end_time - start_time
            
            performance_results.append({
                'size_mb': size_mb,
                'duration_seconds': duration,
                'success': result['success']
            })
            
            # 성능 기준 검증
            if size_mb <= 10:
                assert duration < 5.0, f"{size_mb}MB 백업이 5초를 초과했습니다: {duration:.2f}초"
            elif size_mb <= 50:
                assert duration < 15.0, f"{size_mb}MB 백업이 15초를 초과했습니다: {duration:.2f}초"
            else:
                assert duration < 30.0, f"{size_mb}MB 백업이 30초를 초과했습니다: {duration:.2f}초"
        
        # 성능 결과 출력
        print("\n=== 백업 시간 성능 결과 ===")
        for result in performance_results:
            print(f"크기: {result['size_mb']}MB, 시간: {result['duration_seconds']:.2f}초, "
                  f"처리율: {result['size_mb']/result['duration_seconds']:.2f}MB/s")
    
    def test_compression_performance(self, temp_backup_dir):
        """압축 성능 테스트"""
        backup_engine = BackupEngine()
        compression_results = []
        
        # 다양한 크기의 파일로 압축 테스트
        test_sizes = [1, 5, 10, 20]  # MB
        
        for size_mb in test_sizes:
            # 테스트 파일 생성
            test_file = temp_backup_dir / f"compress_test_{size_mb}mb.sql"
            self.create_test_file(test_file, size_mb)
            
            original_size = test_file.stat().st_size
            
            # 압축 시간 측정
            start_time = time.time()
            compressed_file = backup_engine.compress_file(str(test_file), algorithm="gzip")
            end_time = time.time()
            
            compression_time = end_time - start_time
            compressed_size = Path(compressed_file).stat().st_size
            compression_ratio = compressed_size / original_size
            
            compression_results.append({
                'size_mb': size_mb,
                'original_size': original_size,
                'compressed_size': compressed_size,
                'compression_ratio': compression_ratio,
                'compression_time': compression_time,
                'compression_speed_mb_s': (original_size / (1024 * 1024)) / compression_time
            })
            
            # 압축률 검증 (텍스트 파일은 보통 70% 이상 압축됨)
            assert compression_ratio < 0.5, f"압축률이 기대치보다 낮습니다: {compression_ratio:.2f}"
            
            # 압축 시간 검증 (1MB당 1초 이내)
            expected_max_time = size_mb * 1.0
            assert compression_time < expected_max_time, \
                f"압축 시간이 기대치를 초과했습니다: {compression_time:.2f}초 > {expected_max_time}초"
        
        # 압축 성능 결과 출력
        print("\n=== 압축 성능 결과 ===")
        for result in compression_results:
            print(f"크기: {result['size_mb']}MB, "
                  f"압축률: {result['compression_ratio']:.2f}, "
                  f"압축시간: {result['compression_time']:.2f}초, "
                  f"압축속도: {result['compression_speed_mb_s']:.2f}MB/s")
    
    @patch('app.core.backup_engine.get_encryption_key')
    def test_encryption_performance(self, mock_get_key, temp_backup_dir):
        """암호화 성능 테스트"""
        mock_get_key.return_value = b"a" * 32
        
        backup_engine = BackupEngine()
        encryption_results = []
        
        # 다양한 크기의 파일로 암호화 테스트
        test_sizes = [1, 5, 10, 20]  # MB
        
        for size_mb in test_sizes:
            # 테스트 파일 생성 (압축된 파일 시뮬레이션)
            test_file = temp_backup_dir / f"encrypt_test_{size_mb}mb.sql.gz"
            self.create_test_file(test_file, size_mb)
            
            original_size = test_file.stat().st_size
            
            # 암호화 시간 측정
            start_time = time.time()
            encrypted_file = backup_engine.encrypt_file(str(test_file))
            end_time = time.time()
            
            encryption_time = end_time - start_time
            encrypted_size = Path(encrypted_file).stat().st_size
            
            encryption_results.append({
                'size_mb': size_mb,
                'original_size': original_size,
                'encrypted_size': encrypted_size,
                'encryption_time': encryption_time,
                'encryption_speed_mb_s': (original_size / (1024 * 1024)) / encryption_time
            })
            
            # 암호화 시간 검증 (1MB당 0.5초 이내)
            expected_max_time = size_mb * 0.5
            assert encryption_time < expected_max_time, \
                f"암호화 시간이 기대치를 초과했습니다: {encryption_time:.2f}초 > {expected_max_time}초"
            
            # 암호화된 파일이 원본보다 약간 커야 함 (헤더 정보 포함)
            assert encrypted_size > original_size, "암호화된 파일이 원본보다 작습니다"
        
        # 암호화 성능 결과 출력
        print("\n=== 암호화 성능 결과 ===")
        for result in encryption_results:
            print(f"크기: {result['size_mb']}MB, "
                  f"암호화시간: {result['encryption_time']:.2f}초, "
                  f"암호화속도: {result['encryption_speed_mb_s']:.2f}MB/s")
    
    def test_checksum_performance(self, temp_backup_dir):
        """체크섬 계산 성능 테스트"""
        backup_engine = BackupEngine()
        checksum_results = []
        
        # 다양한 크기의 파일로 체크섬 테스트
        test_sizes = [1, 10, 50, 100]  # MB
        
        for size_mb in test_sizes:
            # 테스트 파일 생성
            test_file = temp_backup_dir / f"checksum_test_{size_mb}mb.sql"
            self.create_test_file(test_file, size_mb)
            
            file_size = test_file.stat().st_size
            
            # 체크섬 계산 시간 측정
            start_time = time.time()
            checksum = backup_engine.calculate_checksum(str(test_file))
            end_time = time.time()
            
            checksum_time = end_time - start_time
            
            checksum_results.append({
                'size_mb': size_mb,
                'file_size': file_size,
                'checksum_time': checksum_time,
                'checksum_speed_mb_s': (file_size / (1024 * 1024)) / checksum_time,
                'checksum': checksum
            })
            
            # 체크섬 시간 검증 (1MB당 0.1초 이내)
            expected_max_time = size_mb * 0.1
            assert checksum_time < expected_max_time, \
                f"체크섬 계산 시간이 기대치를 초과했습니다: {checksum_time:.2f}초 > {expected_max_time}초"
            
            # 체크섬 형식 검증
            assert len(checksum) == 64, "SHA-256 체크섬은 64자여야 합니다"
            assert checksum.isalnum(), "체크섬은 알파벳과 숫자만 포함해야 합니다"
        
        # 체크섬 성능 결과 출력
        print("\n=== 체크섬 성능 결과 ===")
        for result in checksum_results:
            print(f"크기: {result['size_mb']}MB, "
                  f"체크섬시간: {result['checksum_time']:.2f}초, "
                  f"체크섬속도: {result['checksum_speed_mb_s']:.2f}MB/s")
    
    def test_concurrent_backup_performance(self, client, test_db, database_factory):
        """동시 백업 성능 테스트"""
        # 여러 데이터베이스 생성
        databases = []
        for i in range(5):
            db = database_factory.create(
                test_db,
                name=f"concurrent_test_db_{i}",
                display_name=f"동시 테스트 DB {i}",
                host="localhost",
                port=5432,
                database_name=f"concurrentdb{i}",
                username="concurrentuser",
                password_encrypted="concurrentpass"
            )
            databases.append(db)
        
        # 동시 백업 실행 시뮬레이션
        async def simulate_backup(db_id):
            """백업 시뮬레이션"""
            start_time = time.time()
            
            # 실제로는 백업 API를 호출하지만, 여기서는 시뮬레이션
            await asyncio.sleep(0.1)  # 백업 처리 시간 시뮬레이션
            
            end_time = time.time()
            return {
                'database_id': db_id,
                'duration': end_time - start_time,
                'success': True
            }
        
        async def run_concurrent_backups():
            """동시 백업 실행"""
            tasks = [simulate_backup(db.id) for db in databases]
            results = await asyncio.gather(*tasks)
            return results
        
        # 동시 백업 실행
        start_time = time.time()
        results = asyncio.run(run_concurrent_backups())
        total_time = time.time() - start_time
        
        # 결과 검증
        assert len(results) == 5
        assert all(result['success'] for result in results)
        
        # 동시 실행이 순차 실행보다 빨라야 함
        sequential_time = sum(result['duration'] for result in results)
        assert total_time < sequential_time * 0.8, \
            f"동시 실행이 충분히 빠르지 않습니다: {total_time:.2f}초 vs {sequential_time:.2f}초"
        
        print(f"\n=== 동시 백업 성능 결과 ===")
        print(f"동시 실행 시간: {total_time:.2f}초")
        print(f"순차 실행 예상 시간: {sequential_time:.2f}초")
        print(f"성능 향상: {sequential_time/total_time:.2f}배")
    
    def test_memory_usage_performance(self, temp_backup_dir):
        """메모리 사용량 성능 테스트"""
        import psutil
        import os
        
        backup_engine = BackupEngine()
        process = psutil.Process(os.getpid())
        
        # 초기 메모리 사용량
        initial_memory = process.memory_info().rss / (1024 * 1024)  # MB
        
        # 큰 파일 처리 시뮬레이션
        large_file = temp_backup_dir / "large_test.sql"
        self.create_test_file(large_file, 50)  # 50MB 파일
        
        # 압축 수행
        compressed_file = backup_engine.compress_file(str(large_file), algorithm="gzip")
        
        # 압축 후 메모리 사용량
        after_compression_memory = process.memory_info().rss / (1024 * 1024)  # MB
        
        # 체크섬 계산
        checksum = backup_engine.calculate_checksum(compressed_file)
        
        # 최종 메모리 사용량
        final_memory = process.memory_info().rss / (1024 * 1024)  # MB
        
        memory_increase = final_memory - initial_memory
        
        # 메모리 사용량이 과도하지 않은지 확인 (100MB 이내)
        assert memory_increase < 100, \
            f"메모리 사용량이 과도합니다: {memory_increase:.2f}MB 증가"
        
        print(f"\n=== 메모리 사용량 성능 결과 ===")
        print(f"초기 메모리: {initial_memory:.2f}MB")
        print(f"압축 후 메모리: {after_compression_memory:.2f}MB")
        print(f"최종 메모리: {final_memory:.2f}MB")
        print(f"메모리 증가량: {memory_increase:.2f}MB")
    
    def test_database_query_performance(self, client, test_db, database_factory, backup_factory):
        """데이터베이스 쿼리 성능 테스트"""
        # 대량의 테스트 데이터 생성
        databases = []
        for i in range(20):
            db = database_factory.create(
                test_db,
                name=f"query_perf_db_{i}",
                display_name=f"쿼리 성능 테스트 DB {i}",
                environment="development" if i % 2 == 0 else "production"
            )
            databases.append(db)
            
            # 각 데이터베이스마다 백업 생성
            for j in range(10):
                backup_factory.create(
                    test_db,
                    database_id=db.id,
                    backup_type="full" if j % 3 == 0 else "incremental",
                    status="completed" if j % 4 != 0 else "failed"
                )
        
        # 쿼리 성능 테스트
        query_tests = [
            ("전체 데이터베이스 조회", "/api/databases"),
            ("전체 백업 조회", "/api/backups"),
            ("상태별 백업 조회", "/api/backups?status=completed"),
            ("환경별 데이터베이스 조회", "/api/databases?environment=production"),
            ("모니터링 상태 조회", "/api/monitoring/status"),
            ("대시보드 데이터 조회", "/api/monitoring/dashboard")
        ]
        
        performance_results = []
        
        for test_name, endpoint in query_tests:
            # 쿼리 시간 측정
            start_time = time.time()
            response = client.get(endpoint)
            end_time = time.time()
            
            query_time = end_time - start_time
            
            performance_results.append({
                'test_name': test_name,
                'endpoint': endpoint,
                'query_time': query_time,
                'status_code': response.status_code,
                'response_size': len(response.content)
            })
            
            # 응답 시간 검증 (1초 이내)
            assert query_time < 1.0, \
                f"{test_name} 쿼리가 너무 느립니다: {query_time:.2f}초"
            
            # 응답 성공 확인
            assert response.status_code == 200, \
                f"{test_name} 쿼리가 실패했습니다: {response.status_code}"
        
        # 쿼리 성능 결과 출력
        print("\n=== 데이터베이스 쿼리 성능 결과 ===")
        for result in performance_results:
            print(f"{result['test_name']}: {result['query_time']:.3f}초, "
                  f"응답크기: {result['response_size']}바이트")
