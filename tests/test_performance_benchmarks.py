"""
다중 DB 성능/부하 테스트
- 덤프 시간 측정
- 파일 크기 비교
- 압축률 분석
- 메모리 사용량 모니터링

주의:
- 성능 테스트는 시간이 오래 걸릴 수 있음
- 테스트 데이터 크기에 따라 결과가 달라짐
- 시스템 리소스 모니터링 필요
"""

import os
import time
import psutil
import sqlite3
import tempfile
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Any
from unittest.mock import Mock, patch

import pytest

from app.core.backup_adapters import create_backup_adapter
from app.core.backup_postprocessor import backup_postprocessor


class PerformanceMonitor:
    """성능 모니터링 유틸리티"""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.peak_memory = 0
        self.peak_cpu = 0
        self.monitoring = False
        self.monitor_thread = None
    
    def start_monitoring(self):
        """모니터링 시작"""
        self.start_time = time.time()
        self.peak_memory = 0
        self.peak_cpu = 0
        self.monitoring = True
        
        self.monitor_thread = threading.Thread(target=self._monitor_resources)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
    
    def stop_monitoring(self) -> Dict[str, Any]:
        """모니터링 종료 및 결과 반환"""
        self.end_time = time.time()
        self.monitoring = False
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)
        
        return {
            "duration_seconds": self.end_time - self.start_time,
            "peak_memory_mb": self.peak_memory / (1024 * 1024),
            "peak_cpu_percent": self.peak_cpu
        }
    
    def _monitor_resources(self):
        """리소스 모니터링 스레드"""
        process = psutil.Process()
        
        while self.monitoring:
            try:
                # 메모리 사용량
                memory_info = process.memory_info()
                self.peak_memory = max(self.peak_memory, memory_info.rss)
                
                # CPU 사용률
                cpu_percent = process.cpu_percent()
                self.peak_cpu = max(self.peak_cpu, cpu_percent)
                
                time.sleep(0.1)  # 100ms 간격으로 모니터링
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break


class TestDataGenerator:
    """테스트 데이터 생성기"""
    
    @staticmethod
    def create_large_sqlite_db(db_path: Path, num_records: int = 10000) -> Dict[str, Any]:
        """대용량 SQLite 테스트 DB 생성"""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 테이블 생성
        cursor.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                email TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                profile_data TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                product_name TEXT,
                quantity INTEGER,
                price DECIMAL(10,2),
                order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE logs (
                id INTEGER PRIMARY KEY,
                level TEXT,
                message TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        """)
        
        # 인덱스 생성
        cursor.execute("CREATE INDEX idx_users_email ON users(email)")
        cursor.execute("CREATE INDEX idx_orders_user_id ON orders(user_id)")
        cursor.execute("CREATE INDEX idx_logs_level ON logs(level)")
        
        # 대량 데이터 삽입
        import random
        import string
        
        # 사용자 데이터
        users_data = []
        for i in range(num_records):
            username = f"user_{i:06d}"
            email = f"user{i}@example.com"
            profile_data = ''.join(random.choices(string.ascii_letters + string.digits, k=200))
            users_data.append((username, email, profile_data))
        
        cursor.executemany(
            "INSERT INTO users (username, email, profile_data) VALUES (?, ?, ?)",
            users_data
        )
        
        # 주문 데이터 (사용자당 평균 3개 주문)
        orders_data = []
        for i in range(num_records * 3):
            user_id = random.randint(1, num_records)
            product_name = f"Product_{random.randint(1, 1000)}"
            quantity = random.randint(1, 10)
            price = round(random.uniform(10.0, 1000.0), 2)
            orders_data.append((user_id, product_name, quantity, price))
        
        cursor.executemany(
            "INSERT INTO orders (user_id, product_name, quantity, price) VALUES (?, ?, ?, ?)",
            orders_data
        )
        
        # 로그 데이터 (대량)
        log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        logs_data = []
        for i in range(num_records * 5):
            level = random.choice(log_levels)
            message = f"Log message {i}: " + ''.join(random.choices(string.ascii_letters + ' ', k=100))
            metadata = '{"key": "value", "number": ' + str(random.randint(1, 1000)) + '}'
            logs_data.append((level, message, metadata))
        
        cursor.executemany(
            "INSERT INTO logs (level, message, metadata) VALUES (?, ?, ?)",
            logs_data
        )
        
        conn.commit()
        conn.close()
        
        # DB 통계 반환
        db_size = db_path.stat().st_size
        return {
            "db_size_bytes": db_size,
            "db_size_mb": db_size / (1024 * 1024),
            "num_users": num_records,
            "num_orders": num_records * 3,
            "num_logs": num_records * 5,
            "total_records": num_records + (num_records * 3) + (num_records * 5)
        }


class TestBackupPerformance:
    """백업 성능 테스트"""
    
    @pytest.fixture(scope="class")
    def large_sqlite_db(self):
        """대용량 SQLite 테스트 DB"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        
        # 10,000개 레코드로 테스트 DB 생성
        db_stats = TestDataGenerator.create_large_sqlite_db(db_path, 10000)
        
        yield db_path, db_stats
        
        # 정리
        try:
            db_path.unlink()
        except FileNotFoundError:
            pass
    
    def test_sqlite_backup_performance_comparison(self, large_sqlite_db):
        """SQLite 백업 방식별 성능 비교"""
        db_path, db_stats = large_sqlite_db
        adapter = create_backup_adapter("sqlite", "perf_test")
        
        results = {}
        
        # 1. backup API 방식
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_path = Path(temp_dir) / "backup_api.db"
            monitor = PerformanceMonitor()
            
            monitor.start_monitoring()
            success, error, metadata = adapter.run_backup(
                host="localhost",
                port=0,
                dbname=str(db_path),
                user="",
                password="",
                output_path=backup_path,
                options={"method": "backup_api", "vacuum": False, "wal_checkpoint": False}
            )
            perf_stats = monitor.stop_monitoring()
            
            assert success is True
            backup_size = backup_path.stat().st_size
            
            results["backup_api"] = {
                "duration_seconds": perf_stats["duration_seconds"],
                "peak_memory_mb": perf_stats["peak_memory_mb"],
                "backup_size_bytes": backup_size,
                "backup_size_mb": backup_size / (1024 * 1024),
                "compression_ratio": (backup_size / db_stats["db_size_bytes"]) * 100
            }
        
        # 2. 파일 복사 방식
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_path = Path(temp_dir) / "backup_copy.db"
            monitor = PerformanceMonitor()
            
            monitor.start_monitoring()
            success, error, metadata = adapter.run_backup(
                host="localhost",
                port=0,
                dbname=str(db_path),
                user="",
                password="",
                output_path=backup_path,
                options={"method": "file_copy", "wal_checkpoint": False}
            )
            perf_stats = monitor.stop_monitoring()
            
            assert success is True
            backup_size = backup_path.stat().st_size
            
            results["file_copy"] = {
                "duration_seconds": perf_stats["duration_seconds"],
                "peak_memory_mb": perf_stats["peak_memory_mb"],
                "backup_size_bytes": backup_size,
                "backup_size_mb": backup_size / (1024 * 1024),
                "compression_ratio": (backup_size / db_stats["db_size_bytes"]) * 100
            }
        
        # 3. SQL 덤프 방식
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_path = Path(temp_dir) / "backup_dump.sql"
            monitor = PerformanceMonitor()
            
            monitor.start_monitoring()
            success, error, metadata = adapter.run_backup(
                host="localhost",
                port=0,
                dbname=str(db_path),
                user="",
                password="",
                output_path=backup_path,
                options={"method": "dump"}
            )
            perf_stats = monitor.stop_monitoring()
            
            assert success is True
            backup_size = backup_path.stat().st_size
            
            results["dump"] = {
                "duration_seconds": perf_stats["duration_seconds"],
                "peak_memory_mb": perf_stats["peak_memory_mb"],
                "backup_size_bytes": backup_size,
                "backup_size_mb": backup_size / (1024 * 1024),
                "compression_ratio": (backup_size / db_stats["db_size_bytes"]) * 100
            }
        
        # 결과 출력 및 검증
        print(f"\n=== SQLite 백업 성능 비교 ===")
        print(f"원본 DB 크기: {db_stats['db_size_mb']:.2f} MB")
        print(f"총 레코드 수: {db_stats['total_records']:,}")
        
        for method, stats in results.items():
            print(f"\n[{method}]")
            print(f"  소요 시간: {stats['duration_seconds']:.2f}초")
            print(f"  최대 메모리: {stats['peak_memory_mb']:.2f} MB")
            print(f"  백업 크기: {stats['backup_size_mb']:.2f} MB")
            print(f"  압축률: {stats['compression_ratio']:.1f}%")
        
        # 성능 기준 검증
        for method, stats in results.items():
            assert stats["duration_seconds"] < 60  # 1분 이내
            assert stats["peak_memory_mb"] < 500   # 500MB 이내
            assert stats["backup_size_bytes"] > 0  # 백업 파일 생성됨


class TestCompressionPerformance:
    """압축 성능 테스트"""
    
    @pytest.fixture
    def test_backup_file(self):
        """테스트용 백업 파일 생성"""
        with tempfile.NamedTemporaryFile(mode='w', suffix=".sql", delete=False) as f:
            # SQL 덤프 형태의 테스트 데이터 생성
            f.write("-- Test SQL Dump\n")
            f.write("CREATE TABLE test_table (id INTEGER, data TEXT);\n")
            
            # 반복적인 INSERT 문 생성 (압축 효과 확인용)
            for i in range(10000):
                f.write(f"INSERT INTO test_table VALUES ({i}, 'test_data_{i:06d}_{'x' * 50}');\n")
            
            f.write("COMMIT;\n")
            test_file = Path(f.name)
        
        yield test_file
        
        # 정리
        try:
            test_file.unlink()
        except FileNotFoundError:
            pass
    
    def test_compression_algorithms_performance(self, test_backup_file):
        """압축 알고리즘별 성능 비교"""
        original_size = test_backup_file.stat().st_size
        available_tools = backup_postprocessor.get_available_compression_tools()
        
        results = {}
        
        for algorithm in ["gzip", "lz4", "zstd"]:
            if not available_tools.get(algorithm, False):
                print(f"⚠️  {algorithm} 압축 도구를 사용할 수 없습니다.")
                continue
            
            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / f"compressed.{algorithm}"
                monitor = PerformanceMonitor()
                
                # 압축 성능 측정
                monitor.start_monitoring()
                success, error, metadata = backup_postprocessor.compress_file(
                    test_backup_file, output_path, algorithm, 6
                )
                perf_stats = monitor.stop_monitoring()
                
                if success:
                    compressed_size = output_path.stat().st_size
                    compression_ratio = (compressed_size / original_size) * 100
                    compression_speed = original_size / perf_stats["duration_seconds"] / (1024 * 1024)  # MB/s
                    
                    results[algorithm] = {
                        "duration_seconds": perf_stats["duration_seconds"],
                        "peak_memory_mb": perf_stats["peak_memory_mb"],
                        "compressed_size_bytes": compressed_size,
                        "compression_ratio": compression_ratio,
                        "compression_speed_mbps": compression_speed
                    }
        
        # 결과 출력
        print(f"\n=== 압축 알고리즘 성능 비교 ===")
        print(f"원본 파일 크기: {original_size / (1024 * 1024):.2f} MB")
        
        for algorithm, stats in results.items():
            print(f"\n[{algorithm}]")
            print(f"  압축 시간: {stats['duration_seconds']:.2f}초")
            print(f"  압축 속도: {stats['compression_speed_mbps']:.2f} MB/s")
            print(f"  압축률: {stats['compression_ratio']:.1f}%")
            print(f"  메모리 사용: {stats['peak_memory_mb']:.2f} MB")
        
        # 성능 기준 검증
        assert len(results) > 0, "사용 가능한 압축 도구가 없습니다"
        
        for algorithm, stats in results.items():
            assert stats["compression_ratio"] < 100  # 압축 효과 있음
            assert stats["compression_speed_mbps"] > 1  # 최소 1MB/s 이상


class TestConcurrentBackupPerformance:
    """동시 백업 성능 테스트"""
    
    def test_concurrent_sqlite_backups(self):
        """동시 SQLite 백업 성능 테스트"""
        num_concurrent = 3
        num_records_per_db = 5000
        
        # 여러 테스트 DB 생성
        test_dbs = []
        for i in range(num_concurrent):
            with tempfile.NamedTemporaryFile(suffix=f"_test_{i}.db", delete=False) as f:
                db_path = Path(f.name)
            
            TestDataGenerator.create_large_sqlite_db(db_path, num_records_per_db)
            test_dbs.append(db_path)
        
        try:
            # 동시 백업 실행
            import concurrent.futures
            
            def backup_single_db(db_path: Path, backup_id: str) -> Dict[str, Any]:
                adapter = create_backup_adapter("sqlite", backup_id)
                
                with tempfile.TemporaryDirectory() as temp_dir:
                    backup_path = Path(temp_dir) / f"backup_{backup_id}.db"
                    monitor = PerformanceMonitor()
                    
                    monitor.start_monitoring()
                    success, error, metadata = adapter.run_backup(
                        host="localhost",
                        port=0,
                        dbname=str(db_path),
                        user="",
                        password="",
                        output_path=backup_path
                    )
                    perf_stats = monitor.stop_monitoring()
                    
                    return {
                        "backup_id": backup_id,
                        "success": success,
                        "error": error,
                        "duration_seconds": perf_stats["duration_seconds"],
                        "peak_memory_mb": perf_stats["peak_memory_mb"],
                        "backup_size_bytes": backup_path.stat().st_size if success else 0
                    }
            
            # 동시 실행
            overall_start = time.time()
            with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent) as executor:
                futures = [
                    executor.submit(backup_single_db, db_path, f"concurrent_{i}")
                    for i, db_path in enumerate(test_dbs)
                ]
                
                results = [future.result() for future in concurrent.futures.as_completed(futures)]
            overall_duration = time.time() - overall_start
            
            # 결과 분석
            print(f"\n=== 동시 백업 성능 테스트 ===")
            print(f"동시 백업 수: {num_concurrent}")
            print(f"전체 소요 시간: {overall_duration:.2f}초")
            
            successful_backups = [r for r in results if r["success"]]
            assert len(successful_backups) == num_concurrent, "모든 백업이 성공해야 함"
            
            avg_duration = sum(r["duration_seconds"] for r in successful_backups) / len(successful_backups)
            max_duration = max(r["duration_seconds"] for r in successful_backups)
            total_memory = sum(r["peak_memory_mb"] for r in successful_backups)
            
            print(f"평균 백업 시간: {avg_duration:.2f}초")
            print(f"최대 백업 시간: {max_duration:.2f}초")
            print(f"총 메모리 사용량: {total_memory:.2f} MB")
            
            # 성능 기준 검증
            assert overall_duration < max_duration * 2  # 병렬 처리 효과 확인
            assert total_memory < 1000  # 총 1GB 이내
            
        finally:
            # 정리
            for db_path in test_dbs:
                try:
                    db_path.unlink()
                except FileNotFoundError:
                    pass


class TestMemoryLeakDetection:
    """메모리 누수 감지 테스트"""
    
    def test_repeated_backup_memory_usage(self):
        """반복 백업 시 메모리 사용량 테스트"""
        # 작은 테스트 DB 생성
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        
        TestDataGenerator.create_large_sqlite_db(db_path, 1000)  # 작은 DB
        
        try:
            adapter = create_backup_adapter("sqlite", "memory_test")
            memory_usage = []
            
            # 10번 반복 백업
            for i in range(10):
                with tempfile.TemporaryDirectory() as temp_dir:
                    backup_path = Path(temp_dir) / f"backup_{i}.db"
                    
                    # 백업 전 메모리 사용량
                    process = psutil.Process()
                    memory_before = process.memory_info().rss
                    
                    success, error, metadata = adapter.run_backup(
                        host="localhost",
                        port=0,
                        dbname=str(db_path),
                        user="",
                        password="",
                        output_path=backup_path
                    )
                    
                    # 백업 후 메모리 사용량
                    memory_after = process.memory_info().rss
                    memory_usage.append({
                        "iteration": i,
                        "memory_before_mb": memory_before / (1024 * 1024),
                        "memory_after_mb": memory_after / (1024 * 1024),
                        "memory_diff_mb": (memory_after - memory_before) / (1024 * 1024)
                    })
                    
                    assert success is True
            
            # 메모리 사용량 분석
            print(f"\n=== 메모리 누수 감지 테스트 ===")
            for usage in memory_usage:
                print(f"반복 {usage['iteration']}: "
                      f"전 {usage['memory_before_mb']:.2f}MB, "
                      f"후 {usage['memory_after_mb']:.2f}MB, "
                      f"차이 {usage['memory_diff_mb']:.2f}MB")
            
            # 메모리 누수 검증
            initial_memory = memory_usage[0]["memory_before_mb"]
            final_memory = memory_usage[-1]["memory_after_mb"]
            memory_growth = final_memory - initial_memory
            
            print(f"초기 메모리: {initial_memory:.2f}MB")
            print(f"최종 메모리: {final_memory:.2f}MB")
            print(f"메모리 증가: {memory_growth:.2f}MB")
            
            # 메모리 증가가 50MB 이내여야 함 (메모리 누수 없음)
            assert memory_growth < 50, f"메모리 누수 의심: {memory_growth:.2f}MB 증가"
            
        finally:
            try:
                db_path.unlink()
            except FileNotFoundError:
                pass


if __name__ == "__main__":
    # 성능 테스트는 시간이 오래 걸리므로 별도 실행
    pytest.main([__file__, "-v", "-s", "--tb=short"])
