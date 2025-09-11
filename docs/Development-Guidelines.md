# 클라우드 데이터베이스 백업 시스템 개발 지침서

## 📋 개요

이 문서는 클라우드 데이터베이스 자동 백업 시스템 개발 시 각 목차별로 준수해야 하는 지침과 가이드라인을 제공합니다.

---

## 1. 프로젝트 개요 개발 지침

### 1.1 목적 구현 시 고려사항

- **자동화 우선**: 모든 백업 과정은 사용자 개입 없이 자동으로 실행되어야 함
- **안정성 보장**: 데이터 손실 방지를 위한 다중 검증 시스템 구현
- **확장성 고려**: 향후 다른 데이터베이스 시스템 지원 가능한 구조 설계
- **운영 효율성**: 최소한의 리소스로 최대 효과를 내는 최적화 필수

### 1.2 핵심 기능 구현 우선순위

1. **1순위**: 다중 데이터베이스 지원 및 기본 백업 기능
2. **2순위**: 스케줄링 및 자동화 시스템
3. **3순위**: 웹 인터페이스 및 모니터링
4. **4순위**: 고급 기능 (증분 백업, 암호화)

---

## 2. 기술 스택 개발 지침

### 2.1 백엔드 기술 준수사항

- **Python 3.8+ 필수**: 타입 힌트 및 최신 문법 활용
- **FastAPI 사용**: 자동 API 문서화 및 비동기 처리 활용
- **PostgreSQL 메타데이터**: 확장성 및 동시성 지원 우선
- **APScheduler**: 백업 스케줄링의 안정성 보장

### 2.2 의존성 관리 원칙

```python
# requirements.txt 버전 고정 원칙
fastapi==0.104.1  # 메이저 버전 고정
uvicorn>=0.24.0,<0.25.0  # 마이너 버전 범위 지정
psycopg2-binary==2.9.7  # PostgreSQL 동기 드라이버
asyncpg==0.29.0  # PostgreSQL 비동기 드라이버
sqlalchemy==2.0.23  # ORM
alembic==1.13.1  # 마이그레이션 도구
```

### 2.3 코딩 표준

- **변수명**: snake_case 사용, 한글 주석 허용
- **함수명**: 동사\_명사 형태로 명확한 의도 표현
- **클래스명**: PascalCase, 역할을 명확히 표현
- **상수**: UPPER_SNAKE_CASE

---

## 3. 시스템 아키텍처 개발 지침

### 3.1 디렉토리 구조 준수

```
LocalBackUpManager/
├── app/                    # 애플리케이션 코드
│   ├── api/               # API 라우터
│   ├── core/              # 핵심 비즈니스 로직
│   ├── models/            # 데이터 모델
│   └── utils/             # 유틸리티 함수
├── web/                   # 웹 인터페이스
├── data/                  # 데이터 저장소
├── config/                # 설정 파일
└── tests/                 # 테스트 코드
```

### 3.2 모듈 분리 원칙

- **단일 책임**: 각 모듈은 하나의 명확한 역할만 담당
- **느슨한 결합**: 모듈 간 의존성 최소화
- **높은 응집도**: 관련 기능은 같은 모듈에 배치

### 3.3 데이터 플로우 구현

- **비동기 처리**: I/O 집약적 작업은 async/await 사용
- **에러 핸들링**: 각 단계별 예외 처리 및 롤백 메커니즘
- **로깅**: 모든 중요 작업에 대한 상세 로그 기록

---

## 4. 핵심 기능 명세 개발 지침

### 4.1 BackupEngine 구현 지침

```python
class BackupEngine:
    """백업 엔진 구현 시 준수사항"""
    async def execute_full_backup(self, db_id: str) -> BackupResult:
        # 1. 사전 검증: DB 연결, 디스크 공간, 권한 확인
        # 2. 백업 실행: pg_dump 명령어 실행
        # 3. 후처리: 압축, 암호화, 메타데이터 저장
        # 4. 검증: 백업 파일 무결성 확인
        pass
```

### 4.2 에러 처리 원칙

- **예외 계층화**: 비즈니스 로직별 커스텀 예외 정의
- **재시도 로직**: 네트워크 오류 등 일시적 오류에 대한 재시도
- **롤백 메커니즘**: 실패 시 이전 상태로 복구

### 4.3 성능 최적화 지침

- **메모리 관리**: 대용량 파일 처리 시 스트리밍 방식 사용
- **병렬 처리**: CPU 집약적 작업의 멀티프로세싱 활용
- **캐싱**: 자주 사용되는 데이터의 메모리 캐싱

---

## 5. 다중 데이터베이스 지원 개발 지침

### 5.1 설정 파일 관리

```yaml
# databases.yaml 구조 준수
databases:
  db_id:
    name: "사용자 친화적 이름"
    connection:
      host: "호스트 주소"
      port: 5432
      database: "DB명"
      username: "사용자명"
      password: "${ENV_VAR}" # 환경변수 사용 필수
```

### 5.2 연결 관리 원칙

- **연결 풀링**: asyncpg 연결 풀 사용으로 성능 최적화
- **연결 검증**: 정기적인 연결 상태 확인 및 재연결
- **타임아웃 설정**: 모든 DB 작업에 적절한 타임아웃 설정

### 5.3 환경변수 보안

```python
# 환경변수 사용 예시
import os
from cryptography.fernet import Fernet

# 민감 정보는 반드시 환경변수 또는 암호화하여 저장
DB_PASSWORD = os.getenv('DB_PASSWORD')
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')
```

---

## 6. 백업 전략 개발 지침

### 6.1 백업 유형별 구현 방법

```python
# 전체 백업
def full_backup(db_config):
    cmd = f"pg_dump -h {host} -p {port} -U {user} -d {db} -f {output_file}"
    # 압축 옵션 추가: --compress=9

# 증분 백업 (WAL 기반)
def incremental_backup(db_config):
    # WAL 파일 아카이빙 설정 확인
    # pg_receivewal 사용하여 WAL 스트리밍
```

### 6.2 환경별 차등 정책 구현

- **운영환경**: 높은 빈도, 강력한 암호화, 긴 보존 기간
- **스테이징**: 중간 빈도, 선택적 암호화, 중간 보존 기간
- **개발환경**: 낮은 빈도, 암호화 선택, 짧은 보존 기간

### 6.3 우선순위 기반 스케줄링

```python
PRIORITY_CONFIG = {
    'high': {'max_concurrent': 1, 'retry_count': 5},
    'medium': {'max_concurrent': 2, 'retry_count': 3},
    'low': {'max_concurrent': 3, 'retry_count': 1}
}
```

---

## 7. 보안 개발 지침

### 7.1 데이터 암호화 구현

```python
from cryptography.fernet import Fernet

class EncryptionManager:
    def __init__(self, key: str):
        self.cipher = Fernet(key.encode())
    def encrypt_file(self, file_path: str) -> str:
        # AES-256 암호화 구현
        # 암호화된 파일은 .encrypted 확장자 추가
```

### 7.2 접근 제어 구현

- **파일 권한**: 백업 파일 700, 설정 파일 600
- **디렉토리 권한**: 백업 디렉토리 700
- **사용자 분리**: 백업 전용 사용자 계정 사용 권장

### 7.3 네트워크 보안

```python
# SSL/TLS 연결 강제
connection_params = {
    'sslmode': 'require',
    'sslcert': 'client-cert.pem',
    'sslkey': 'client-key.pem',
    'sslrootcert': 'ca-cert.pem'
}
```

---

## 8. 모니터링 및 알림 개발 지침

### 8.1 모니터링 메트릭 수집

```python
# 필수 모니터링 항목
MONITORING_METRICS = {
    'backup_success_rate': '백업 성공률',
    'backup_duration': '백업 소요 시간',
    'backup_file_size': '백업 파일 크기',
    'disk_usage': '디스크 사용량',
    'database_connection_status': 'DB 연결 상태'
}
```

### 8.2 알림 시스템 구현

```python
class NotificationManager:
    async def send_notification(self, level: str, message: str):
        # 알림 레벨에 따른 채널 분기
        if level == 'CRITICAL':
            await self.send_email()
            await self.send_slack()
        elif level == 'WARNING':
            await self.send_slack()
        # 알림 이력 저장 필수
```

### 8.3 계층적 알림 정책

- **CRITICAL**: 운영 DB 백업 실패, 시스템 오류
- **WARNING**: 디스크 공간 부족, 성능 저하
- **INFO**: 백업 완료, 정기 리포트

---

## 9. REST API 명세 개발 지침

### 9.1 API 설계 원칙

```python
# FastAPI 라우터 구조
@router.get("/databases", response_model=List[DatabaseResponse])
async def get_databases():
    """모든 데이터베이스 목록 조회"""
    # 1. 인증/권한 확인
    # 2. 비즈니스 로직 실행
    # 3. 응답 데이터 변환
    # 4. 로그 기록
```

### 9.2 에러 응답 표준화

```python
# 표준 에러 응답 형식
{
    "error": {
        "code": "BACKUP_FAILED",
        "message": "백업 실행 중 오류가 발생했습니다",
        "details": "상세 오류 정보",
        "timestamp": "2024-01-01T00:00:00Z"
    }
}
```

### 9.3 API 문서화

- **자동 문서화**: FastAPI의 자동 스웨거 문서 활용
- **예제 포함**: 모든 엔드포인트에 요청/응답 예제 제공
- **한글 설명**: API 설명은 한글로 작성

---

## 10. 개발 단계별 구현 계획 지침

### 10.1 Phase별 완료 기준 준수

```python
# Phase 1 완료 기준 체크리스트
PHASE1_CHECKLIST = [
    "단일 DB 연결 성공",
    "pg_dump 백업 실행",
    "백업 파일 압축",
    "기본 암호화 적용",
    "메타데이터 저장"
]
```

### 10.2 코드 품질 관리

- **테스트 커버리지**: 각 Phase별 80% 이상 유지
- **코드 리뷰**: 모든 PR에 대한 리뷰 필수
- **정적 분석**: pylint, mypy 사용한 코드 품질 검사

### 10.3 문서화 요구사항

- **API 문서**: 자동 생성된 스웨거 문서
- **개발자 가이드**: 설치, 설정, 사용법 문서
- **운영 가이드**: 배포, 모니터링, 트러블슈팅 가이드

---

## 11. 운영 가이드 개발 지침

### 11.1 설치 스크립트 작성

```bash
#!/bin/bash
# install.sh - 자동 설치 스크립트
set -e

echo "클라우드 데이터베이스 백업 시스템 설치 시작..."
# 1. 시스템 요구사항 확인
# 2. 의존성 설치
# 3. 설정 파일 생성
# 4. 서비스 등록
```

### 11.2 Docker 컨테이너화

```dockerfile
FROM python:3.11-slim

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y postgresql-client

# 애플리케이션 코드 복사
COPY . /app
WORKDIR /app

# 의존성 설치
RUN pip install -r requirements.txt

# 헬스체크 추가
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1
```

### 11.3 모니터링 설정

- **로그 로테이션**: logrotate 설정으로 로그 파일 관리
- **메트릭 수집**: Prometheus 메트릭 엔드포인트 제공
- **알림 설정**: 운영 환경별 알림 채널 구성

---

## 12. 확장성 및 고가용성 개발 지침

### 12.1 수평 확장 설계

```python
# 마스터-워커 아키텍처
class MasterNode:
    def distribute_backup_jobs(self):
        # 워커 노드별 작업 분배 로직
        pass

class WorkerNode:
    def execute_backup_job(self, job):
        # 개별 백업 작업 실행
        pass
```

### 12.2 장애 복구 메커니즘

- **헬스체크**: 정기적인 시스템 상태 확인
- **자동 복구**: 일시적 장애에 대한 자동 재시작
- **페일오버**: 마스터 노드 장애 시 워커 노드 승격

### 12.3 성능 최적화

```python
# 캐싱 전략
from functools import lru_cache

@lru_cache(maxsize=128)
def get_database_info(db_id: str):
    # DB 정보 캐싱으로 성능 향상
    pass
```

---

## 📋 개발 체크리스트

### 코드 작성 전 확인사항

- [ ] 기획서의 해당 섹션 요구사항 숙지
- [ ] 관련 지침 및 표준 확인
- [ ] 의존성 및 버전 호환성 검토
- [ ] 보안 요구사항 확인

### 코드 작성 중 준수사항

- [ ] 타입 힌트 사용
- [ ] 한글 주석 작성
- [ ] 에러 처리 구현
- [ ] 로깅 추가
- [ ] 테스트 코드 작성

### 코드 완료 후 검증사항

- [ ] 단위 테스트 통과
- [ ] 통합 테스트 통과
- [ ] 코드 리뷰 완료
- [ ] 문서 업데이트
- [ ] 성능 테스트 완료

이 지침서를 통해 일관성 있고 품질 높은 클라우드 데이터베이스 백업 시스템을 개발할 수 있습니다.
