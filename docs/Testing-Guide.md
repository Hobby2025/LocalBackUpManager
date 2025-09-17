# 테스트 실행 가이드

## 개요

이 문서는 PostgreSQL 클라우드 데이터베이스 자동 백업 시스템의 테스트 실행 방법을 설명합니다.

## 테스트 환경 설정

### 1. 의존성 설치

```bash
# 가상환경 활성화
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# 테스트 의존성 설치
pip install -r requirements.txt
```

### 2. 환경 변수 설정

테스트용 `.env.test` 파일 생성:

```env
# 테스트 환경 설정
TESTING=true
DEBUG=true
DATABASE_URL=sqlite:///./test.db

# 암호화 키 (테스트용)
ENCRYPTION_KEY=test_encryption_key_32_characters

# PostgreSQL 테스트 설정 (선택사항)
TEST_PG_HOST=localhost
TEST_PG_PORT=5432
TEST_PG_USER=testuser
TEST_PG_PASSWORD=testpass
TEST_PG_DATABASE=testdb
```

## 테스트 실행 방법

### 1. 전체 테스트 실행

```bash
# 모든 테스트 실행 (커버리지 포함)
pytest

# 상세 출력과 함께 실행
pytest -v

# 커버리지 리포트 생성
pytest --cov=app --cov-report=html
```

### 2. 테스트 타입별 실행

#### 단위 테스트

```bash
# 모든 단위 테스트
pytest tests/unit/ -v

# 특정 모듈 단위 테스트
pytest tests/unit/test_database_models.py -v
pytest tests/unit/test_api_databases.py -v
pytest tests/unit/test_backup_engine.py -v
pytest tests/unit/test_audit_service.py -v
```

#### 통합 테스트

```bash
# 모든 통합 테스트
pytest tests/integration/ -v

# 백업 워크플로우 테스트
pytest tests/integration/test_backup_workflow.py -v
```

#### 성능 테스트

```bash
# 모든 성능 테스트 (시간이 오래 걸림)
pytest tests/performance/ -v -m performance

# 특정 성능 테스트
pytest tests/performance/test_backup_performance.py::TestBackupPerformance::test_backup_time_performance -v
```

#### 회귀 테스트

```bash
# 모든 회귀 테스트
pytest tests/regression/ -v -m regression

# PostgreSQL 호환성 테스트
pytest tests/regression/test_postgresql_compatibility.py -v
```

### 3. 마커별 테스트 실행

```bash
# 단위 테스트만 실행
pytest -m unit

# 통합 테스트만 실행
pytest -m integration

# 성능 테스트만 실행
pytest -m performance

# 회귀 테스트만 실행
pytest -m regression

# 느린 테스트 제외하고 실행
pytest -m "not slow"
```

### 4. 특정 테스트 실행

```bash
# 특정 테스트 클래스
pytest tests/unit/test_database_models.py::TestUserModel -v

# 특정 테스트 메서드
pytest tests/unit/test_database_models.py::TestUserModel::test_create_user -v

# 키워드로 테스트 필터링
pytest -k "test_create" -v
pytest -k "database and not performance" -v
```

## 테스트 결과 분석

### 1. 커버리지 리포트

```bash
# HTML 커버리지 리포트 생성
pytest --cov=app --cov-report=html

# 터미널에서 커버리지 확인
pytest --cov=app --cov-report=term-missing

# 커버리지 임계값 설정 (90% 미만 시 실패)
pytest --cov=app --cov-fail-under=90
```

생성된 `htmlcov/index.html` 파일을 브라우저로 열어 상세한 커버리지 정보를 확인할 수 있습니다.

### 2. 테스트 결과 파일

```bash
# JUnit XML 형식으로 결과 저장
pytest --junitxml=test-results.xml

# JSON 형식으로 결과 저장 (pytest-json-report 플러그인 필요)
pytest --json-report --json-report-file=test-results.json
```

## 환경별 테스트 실행

### 1. 로컬 개발 환경

```bash
# 기본 테스트 (빠른 테스트만)
pytest -m "not slow and not performance"

# 개발 중인 기능 테스트
pytest tests/unit/test_new_feature.py -v
```

### 2. CI/CD 환경

```bash
# 전체 테스트 (성능 테스트 제외)
pytest -m "not performance" --cov=app --cov-report=xml

# 병렬 실행 (pytest-xdist 플러그인 사용)
pytest -n auto -m "not performance"
```

### 3. 운영 환경 검증

```bash
# 회귀 테스트만 실행
pytest -m regression -v

# 중요한 기능 테스트만 실행
pytest -m "unit and not slow" -k "test_backup or test_database"
```

## 테스트 데이터 관리

### 1. 테스트 데이터베이스

- 각 테스트는 독립적인 SQLite 인메모리 데이터베이스 사용
- 테스트 간 데이터 격리를 위해 트랜잭션 롤백 사용
- `conftest.py`의 픽스처를 통해 테스트 데이터 자동 생성

### 2. 임시 파일 관리

- 백업 파일 테스트를 위한 임시 디렉토리 자동 생성/정리
- `temp_backup_dir` 픽스처 사용으로 테스트 후 자동 정리

### 3. Mock 데이터

- 외부 의존성(pg_dump, 네트워크 등)은 Mock으로 대체
- 실제 PostgreSQL 서버 없이도 테스트 가능

## 성능 테스트 가이드

### 1. 성능 기준

- **백업 시간**: 10MB 이하 5초, 50MB 이하 15초, 100MB 이하 30초
- **압축률**: 텍스트 파일 기준 50% 이상 압축
- **메모리 사용량**: 100MB 이하 증가
- **API 응답시간**: 1초 이내

### 2. 성능 테스트 실행

```bash
# 성능 테스트 실행 (시간이 오래 걸림)
pytest tests/performance/ -v -s

# 특정 성능 테스트만 실행
pytest tests/performance/test_backup_performance.py::TestBackupPerformance::test_compression_performance -v -s
```

### 3. 성능 결과 해석

성능 테스트 실행 시 콘솔에 출력되는 성능 지표를 확인:

```
=== 백업 시간 성능 결과 ===
크기: 1MB, 시간: 0.15초, 처리율: 6.67MB/s
크기: 10MB, 시간: 1.23초, 처리율: 8.13MB/s
크기: 50MB, 시간: 5.67초, 처리율: 8.82MB/s
```

## 문제 해결

### 1. 일반적인 오류

#### 테스트 데이터베이스 연결 오류

```bash
# 해결방법: 테스트용 SQLite 사용 확인
export DATABASE_URL=sqlite:///./test.db
pytest tests/unit/test_database_models.py -v
```

#### 의존성 오류

```bash
# 해결방법: 테스트 의존성 재설치
pip install -r requirements.txt --force-reinstall
```

#### 권한 오류

```bash
# 해결방법: 테스트 디렉토리 권한 확인
chmod -R 755 tests/
```

### 2. 성능 테스트 오류

#### 메모리 부족

```bash
# 해결방법: 성능 테스트 파일 크기 조정
pytest tests/performance/ -v -k "not test_memory_usage"
```

#### 시간 초과

```bash
# 해결방법: 타임아웃 증가 또는 테스트 제외
pytest tests/performance/ -v -k "not test_concurrent"
```

### 3. Mock 관련 오류

#### pg_dump Mock 실패

```python
# 해결방법: Mock 설정 확인
@patch('subprocess.run')
def test_example(mock_subprocess):
    mock_process = Mock()
    mock_process.returncode = 0
    mock_process.stdout = b"test output"
    mock_subprocess.return_value = mock_process
```

## 테스트 작성 가이드

### 1. 새로운 테스트 추가

```python
# tests/unit/test_new_feature.py
import pytest
from app.new_feature import NewFeature

@pytest.mark.unit
class TestNewFeature:
    def test_new_functionality(self, test_db):
        # Given
        feature = NewFeature()
        
        # When
        result = feature.do_something()
        
        # Then
        assert result is not None
        assert result.success is True
```

### 2. 픽스처 사용

```python
def test_with_database(self, test_db, database_factory):
    # 테스트용 데이터베이스 생성
    database = database_factory.create(test_db, name="test_db")
    
    # 테스트 로직
    assert database.name == "test_db"
```

### 3. Mock 사용

```python
@patch('app.external_service.external_call')
def test_with_mock(self, mock_external):
    mock_external.return_value = {"success": True}
    
    # 테스트 로직
    result = my_function()
    assert result["success"] is True
    mock_external.assert_called_once()
```

## 지속적 통합 (CI)

### 1. GitHub Actions 설정

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.8
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: pytest --cov=app --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v1
```

### 2. 테스트 자동화

- 모든 Pull Request에서 자동 테스트 실행
- 커버리지 90% 이상 유지
- 성능 테스트는 주기적으로 실행

## 참고 자료

- [pytest 공식 문서](https://docs.pytest.org/)
- [pytest-cov 문서](https://pytest-cov.readthedocs.io/)
- [unittest.mock 문서](https://docs.python.org/3/library/unittest.mock.html)
- [FastAPI 테스트 가이드](https://fastapi.tiangolo.com/tutorial/testing/)
