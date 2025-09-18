# 다중 DB 백업 시스템 배포 가이드

## 📋 개요

이 문서는 PostgreSQL, MySQL, SQLite를 지원하는 다중 데이터베이스 백업 시스템의 배포 가이드입니다.

## 🔧 시스템 요구사항

### 최소 요구사항
- **CPU**: 2 cores
- **RAM**: 4GB
- **Storage**: 50GB + 백업 전용 스토리지
- **OS**: Ubuntu 20.04+ / CentOS 8+ / Windows Server 2019+

### 권장 요구사항
- **CPU**: 4+ cores
- **RAM**: 8GB+
- **Storage**: SSD 100GB + 백업 전용 스토리지
- **Network**: 1Gbps+

## 📦 사전 준비

### 1. 데이터베이스 클라이언트 도구 설치

#### Ubuntu/Debian
```bash
# PostgreSQL 클라이언트
sudo apt-get update
sudo apt-get install postgresql-client

# MySQL 클라이언트
sudo apt-get install mysql-client

# SQLite
sudo apt-get install sqlite3

# 압축 도구
sudo apt-get install gzip lz4 zstd
```

#### CentOS/RHEL
```bash
# PostgreSQL 클라이언트
sudo yum install postgresql

# MySQL 클라이언트
sudo yum install mysql

# SQLite
sudo yum install sqlite

# 압축 도구
sudo yum install gzip lz4 zstd
```

#### Windows
```powershell
# Chocolatey 사용
choco install postgresql
choco install mysql.commandline
choco install sqlite

# 또는 직접 다운로드
# PostgreSQL: https://www.postgresql.org/download/windows/
# MySQL: https://dev.mysql.com/downloads/mysql/
# SQLite: https://www.sqlite.org/download.html
```

### 2. Python 환경 설정
```bash
# Python 3.8+ 설치 확인
python3 --version

# 가상환경 생성
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 의존성 설치
pip install -r requirements.txt
```

## 🚀 로컬 개발 환경 배포

### 1. 저장소 클론 및 설정
```bash
git clone https://github.com/your-org/LocalBackUpManager.git
cd LocalBackUpManager

# 설정 파일 복사
cp config/settings.yaml.example config/settings.yaml
cp config/databases.yaml.example config/databases.yaml
cp .env.example .env
```

### 2. 환경변수 설정
```bash
# .env 파일 편집
METADATA_DB_PASSWORD=your_secure_password
ENCRYPTION_KEY=your_32_character_encryption_key
SMTP_USERNAME=your_email@company.com
SMTP_PASSWORD=your_app_password

# 테스트 DB 연결 정보 (선택사항)
TEST_POSTGRES_HOST=localhost
TEST_POSTGRES_PORT=5432
TEST_POSTGRES_DB=test_db
TEST_POSTGRES_USER=test_user
TEST_POSTGRES_PASSWORD=test_pass

TEST_MYSQL_HOST=localhost
TEST_MYSQL_PORT=3306
TEST_MYSQL_DB=test_db
TEST_MYSQL_USER=test_user
TEST_MYSQL_PASSWORD=test_pass
```

### 3. 메타데이터 데이터베이스 초기화
```bash
# PostgreSQL 메타데이터 DB 생성
createdb backup_metadata

# 마이그레이션 실행
alembic upgrade head
```

### 4. 다중 DB 설정 예시

#### databases.yaml 설정
```yaml
databases:
  # PostgreSQL 예시
  local_postgres:
    name: "로컬 PostgreSQL"
    host: "localhost"
    port: 5432
    database: "myapp_db"
    username: "backup_user"
    password: "${LOCAL_POSTGRES_PASSWORD}"
    ssl_mode: "disable"
    db_type: "postgresql"
    priority: "medium"
    environment: "development"

  # MySQL 예시
  local_mysql:
    name: "로컬 MySQL"
    host: "localhost"
    port: 3306
    database: "myapp_db"
    username: "backup_user"
    password: "${LOCAL_MYSQL_PASSWORD}"
    ssl_mode: "disable"
    db_type: "mysql"
    priority: "medium"
    environment: "development"

  # SQLite 예시
  local_sqlite:
    name: "로컬 SQLite"
    host: "localhost"
    port: 0
    database: "/path/to/myapp.db"
    username: ""
    password: ""
    ssl_mode: "disable"
    db_type: "sqlite"
    priority: "low"
    environment: "development"
```

### 5. 애플리케이션 실행
```bash
# 개발 서버 실행
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 또는 프로덕션 모드
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 6. 연결 테스트
```bash
# 웹 인터페이스 접속
http://localhost:8000

# API 헬스체크
curl http://localhost:8000/api/health

# 데이터베이스 연결 테스트
curl -X POST http://localhost:8000/api/databases/{database_id}/test-connection
```

## 🐳 Docker 배포

### 1. Docker Compose 사용 (권장)
```yaml
# docker-compose.yml
version: '3.8'

services:
  backup-manager:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:password@metadata-db:5432/backup_metadata
      - METADATA_DB_PASSWORD=secure_password
      - ENCRYPTION_KEY=your_32_character_encryption_key
    volumes:
      - ./data/backups:/app/data/backups
      - ./data/logs:/app/data/logs
      - ./config:/app/config
    depends_on:
      - metadata-db
      - redis

  metadata-db:
    image: postgres:15
    environment:
      - POSTGRES_DB=backup_metadata
      - POSTGRES_USER=backup_user
      - POSTGRES_PASSWORD=secure_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

### 2. Docker 실행
```bash
# 빌드 및 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f backup-manager

# 마이그레이션 실행
docker-compose exec backup-manager alembic upgrade head
```

### 3. Docker 단독 실행
```bash
# 이미지 빌드
docker build -t backup-manager .

# 컨테이너 실행
docker run -d \
  --name backup-manager \
  -p 8000:8000 \
  -v $(pwd)/data/backups:/app/data/backups \
  -v $(pwd)/config:/app/config \
  -e DATABASE_URL=postgresql://user:password@host:5432/backup_metadata \
  backup-manager
```

## ☸️ Kubernetes 배포

### 1. ConfigMap 생성
```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: backup-manager-config
data:
  settings.yaml: |
    backup:
      base_path: "/app/data/backups"
      temp_path: "/app/data/temp"
      max_parallel_jobs: 3
    compression:
      default_algorithm: "gzip"
      default_level: 6
    encryption:
      enabled: true
```

### 2. Secret 생성
```yaml
# k8s/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: backup-manager-secret
type: Opaque
data:
  database-url: <base64-encoded-database-url>
  encryption-key: <base64-encoded-32-char-key>
  smtp-password: <base64-encoded-smtp-password>
```

### 3. Deployment 생성
```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backup-manager
spec:
  replicas: 2
  selector:
    matchLabels:
      app: backup-manager
  template:
    metadata:
      labels:
        app: backup-manager
    spec:
      containers:
      - name: backup-manager
        image: backup-manager:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: backup-manager-secret
              key: database-url
        - name: ENCRYPTION_KEY
          valueFrom:
            secretKeyRef:
              name: backup-manager-secret
              key: encryption-key
        volumeMounts:
        - name: config
          mountPath: /app/config
        - name: backup-storage
          mountPath: /app/data/backups
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
      volumes:
      - name: config
        configMap:
          name: backup-manager-config
      - name: backup-storage
        persistentVolumeClaim:
          claimName: backup-storage-pvc
```

### 4. Service 생성
```yaml
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: backup-manager-service
spec:
  selector:
    app: backup-manager
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

### 5. Kubernetes 배포 실행
```bash
# 리소스 적용
kubectl apply -f k8s/

# 배포 상태 확인
kubectl get pods
kubectl get services

# 로그 확인
kubectl logs -f deployment/backup-manager
```

## 🏭 운영 환경 배포

### 1. 운영 환경 설정

#### 보안 설정
```yaml
# config/settings.yaml (운영용)
security:
  encryption:
    enabled: true
    key_rotation_days: 90
  authentication:
    session_timeout: 3600
    max_login_attempts: 5
  ssl:
    enabled: true
    cert_path: "/etc/ssl/certs/backup-manager.crt"
    key_path: "/etc/ssl/private/backup-manager.key"

backup:
  base_path: "/data/backups"
  temp_path: "/tmp/backup-temp"
  max_parallel_jobs: 4
  retention:
    daily: 30
    weekly: 12
    monthly: 24

monitoring:
  prometheus:
    enabled: true
    port: 9090
  logging:
    level: "INFO"
    file: "/var/log/backup-manager/app.log"
    max_size: "100MB"
    backup_count: 10
```

#### 데이터베이스 설정
```yaml
# config/databases.yaml (운영용)
databases:
  production_postgres:
    name: "운영 PostgreSQL 클러스터"
    host: "prod-postgres-primary.company.com"
    port: 5432
    database: "production"
    username: "backup_service"
    password: "${PROD_POSTGRES_PASSWORD}"
    ssl_mode: "require"
    db_type: "postgresql"
    priority: "critical"
    environment: "production"
    backup_config:
      full_backup_schedule: "0 2 * * 0"  # 매주 일요일 2시
      incremental_schedule: "0 */6 * * *"  # 6시간마다
      compression: "zstd"
      encryption: true
      retention_policy:
        daily: 30
        weekly: 12
        monthly: 24

  production_mysql:
    name: "운영 MySQL 클러스터"
    host: "prod-mysql-primary.company.com"
    port: 3306
    database: "production"
    username: "backup_service"
    password: "${PROD_MYSQL_PASSWORD}"
    ssl_mode: "require"
    db_type: "mysql"
    priority: "critical"
    environment: "production"
    backup_config:
      full_backup_schedule: "0 3 * * 0"  # 매주 일요일 3시
      incremental_schedule: "0 */8 * * *"  # 8시간마다
      compression: "gzip"
      encryption: true
```

### 2. 시스템 서비스 등록

#### systemd 서비스 (Linux)
```ini
# /etc/systemd/system/backup-manager.service
[Unit]
Description=Multi-Database Backup Manager
After=network.target postgresql.service mysql.service

[Service]
Type=exec
User=backup-manager
Group=backup-manager
WorkingDirectory=/opt/backup-manager
Environment=PATH=/opt/backup-manager/venv/bin
ExecStart=/opt/backup-manager/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=10

# 보안 설정
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/backup-manager/data /var/log/backup-manager

[Install]
WantedBy=multi-user.target
```

#### 서비스 등록 및 시작
```bash
# 서비스 등록
sudo systemctl daemon-reload
sudo systemctl enable backup-manager

# 서비스 시작
sudo systemctl start backup-manager

# 상태 확인
sudo systemctl status backup-manager

# 로그 확인
sudo journalctl -u backup-manager -f
```

### 3. 로드 밸런서 설정

#### Nginx 설정
```nginx
# /etc/nginx/sites-available/backup-manager
upstream backup_manager {
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;  # 다중 인스턴스
}

server {
    listen 80;
    listen 443 ssl http2;
    server_name backup.company.com;

    # SSL 설정
    ssl_certificate /etc/ssl/certs/backup-manager.crt;
    ssl_certificate_key /etc/ssl/private/backup-manager.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;

    # 보안 헤더
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";

    location / {
        proxy_pass http://backup_manager;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 타임아웃 설정 (백업 작업용)
        proxy_connect_timeout 60s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    # 정적 파일 서빙
    location /static/ {
        alias /opt/backup-manager/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

### 4. 모니터링 설정

#### Prometheus 메트릭 수집
```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'backup-manager'
    static_configs:
      - targets: ['backup.company.com:9090']
    scrape_interval: 30s
    metrics_path: /metrics
```

#### Grafana 대시보드
- 백업 성공률
- 백업 소요 시간
- 파일 크기 추이
- 압축률 통계
- 시스템 리소스 사용량

## 🧪 테스트 실행

### 1. 단위 테스트
```bash
# 전체 테스트 실행
pytest

# 다중 DB 통합 테스트
pytest tests/test_multidb_integration.py -v

# 성능 테스트
pytest tests/test_performance_benchmarks.py -v -s

# 회귀 테스트
pytest tests/test_regression_postgresql.py -v

# 커버리지 리포트
pytest --cov=app --cov-report=html
```

### 2. E2E 테스트
```bash
# 실제 DB 연결 테스트 (환경변수 설정 필요)
export TEST_POSTGRES_HOST=localhost
export TEST_POSTGRES_PORT=5432
export TEST_POSTGRES_DB=test_db
export TEST_POSTGRES_USER=test_user
export TEST_POSTGRES_PASSWORD=test_pass

pytest tests/test_multidb_integration.py::TestPostgreSQLIntegration -v
```

### 3. 성능 벤치마크
```bash
# 대용량 데이터 성능 테스트
pytest tests/test_performance_benchmarks.py::TestBackupPerformance -v -s

# 압축 성능 비교
pytest tests/test_performance_benchmarks.py::TestCompressionPerformance -v -s

# 동시 백업 테스트
pytest tests/test_performance_benchmarks.py::TestConcurrentBackupPerformance -v -s
```

## 🔍 트러블슈팅

### 일반적인 문제들

#### 1. 데이터베이스 클라이언트 도구 없음
```bash
# 오류: pg_dump: command not found
# 해결: PostgreSQL 클라이언트 설치
sudo apt-get install postgresql-client

# 오류: mysqldump: command not found  
# 해결: MySQL 클라이언트 설치
sudo apt-get install mysql-client
```

#### 2. 권한 문제
```bash
# 백업 디렉토리 권한 설정
sudo chown -R backup-manager:backup-manager /data/backups
sudo chmod -R 755 /data/backups

# 로그 디렉토리 권한 설정
sudo mkdir -p /var/log/backup-manager
sudo chown backup-manager:backup-manager /var/log/backup-manager
```

#### 3. 메모리 부족
```bash
# 스왑 파일 생성 (임시 해결)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 영구 설정
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

#### 4. 네트워크 연결 문제
```bash
# 방화벽 확인
sudo ufw status
sudo ufw allow 5432/tcp  # PostgreSQL
sudo ufw allow 3306/tcp  # MySQL

# DNS 확인
nslookup your-database-host.com
```

### 로그 분석

#### 애플리케이션 로그
```bash
# 실시간 로그 모니터링
tail -f /var/log/backup-manager/app.log

# 에러 로그 필터링
grep "ERROR" /var/log/backup-manager/app.log

# 백업 관련 로그
grep "backup" /var/log/backup-manager/app.log
```

#### 시스템 로그
```bash
# systemd 서비스 로그
sudo journalctl -u backup-manager -f

# 시스템 리소스 모니터링
htop
iostat -x 1
```

## 📊 성능 최적화

### 1. 데이터베이스 최적화
```sql
-- PostgreSQL 백업 사용자 권한 최적화
GRANT CONNECT ON DATABASE production TO backup_service;
GRANT USAGE ON SCHEMA public TO backup_service;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO backup_service;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO backup_service;

-- MySQL 백업 사용자 권한
GRANT SELECT, LOCK TABLES, SHOW VIEW, EVENT, TRIGGER ON production.* TO 'backup_service'@'%';
FLUSH PRIVILEGES;
```

### 2. 시스템 최적화
```bash
# 파일 디스크립터 제한 증가
echo "backup-manager soft nofile 65536" | sudo tee -a /etc/security/limits.conf
echo "backup-manager hard nofile 65536" | sudo tee -a /etc/security/limits.conf

# 커널 파라미터 조정
echo "net.core.somaxconn = 65535" | sudo tee -a /etc/sysctl.conf
echo "net.ipv4.tcp_max_syn_backlog = 65535" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

### 3. 백업 최적화
```yaml
# config/settings.yaml
backup:
  max_parallel_jobs: 4  # CPU 코어 수에 맞게 조정
  compression:
    algorithm: "zstd"  # 빠른 압축
    level: 3  # 균형잡힌 압축 레벨
  optimization:
    use_connection_pooling: true
    batch_size: 1000
    memory_limit_mb: 512
```

이 가이드를 통해 다중 DB 백업 시스템을 안정적으로 배포하고 운영할 수 있습니다.
