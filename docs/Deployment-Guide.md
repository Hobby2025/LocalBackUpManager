# 배포 가이드

## 개요

이 문서는 PostgreSQL 클라우드 데이터베이스 자동 백업 시스템의 배포 방법을 설명합니다.

## 배포 옵션

### 1. Docker Compose (개발/소규모 운영)
### 2. Kubernetes (대규모 운영)
### 3. 클라우드 서비스 (AWS, GCP, Azure)

## Docker Compose 배포

### 사전 요구사항

- Docker 20.10+
- Docker Compose 2.0+
- 최소 4GB RAM, 2 CPU 코어
- 50GB 이상 디스크 공간

### 1. 환경 설정

```bash
# 프로젝트 클론
git clone https://github.com/your-org/backup-manager.git
cd backup-manager

# 환경 변수 파일 생성
cp .env.example .env
```

`.env` 파일 설정:

```env
# 기본 설정
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=info

# 암호화 키 (32자)
ENCRYPTION_KEY=your_32_character_encryption_key_here

# 데이터베이스 설정
POSTGRES_DB=backup_manager
POSTGRES_USER=backup_user
POSTGRES_PASSWORD=secure_password_here

# 알림 설정
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# 백업 대상 데이터베이스 (예시)
PROD_DB_HOST=your-prod-db-host
PROD_DB_NAME=your-prod-db-name
PROD_DB_USER=your-prod-db-user
PROD_DB_PASSWORD=your-prod-db-password
```

### 2. 디렉토리 구조 생성

```bash
# 데이터 디렉토리 생성
mkdir -p data/{backups,logs,reports}
mkdir -p nginx/ssl
mkdir -p monitoring/{prometheus,grafana}

# 권한 설정
chmod -R 755 data/
```

### 3. 설정 파일 준비

`config/settings.yaml` 파일 생성:

```yaml
app:
  name: "PostgreSQL Backup Manager"
  version: "1.0.0"
  environment: "production"

backup:
  retention_days: 30
  max_size_gb: 10
  compression: "gzip"

notifications:
  enabled: true
  channels:
    - email
    - slack
```

### 4. 배포 실행

```bash
# 프로덕션 배포
docker-compose up -d

# 로그 확인
docker-compose logs -f app

# 상태 확인
docker-compose ps
```

### 5. 초기 설정

```bash
# 데이터베이스 마이그레이션
docker-compose exec app alembic upgrade head

# 관리자 계정 생성
docker-compose exec app python -m app.scripts.create_admin

# 헬스체크
curl http://localhost:8000/api/health
```

## Kubernetes 배포

### 사전 요구사항

- Kubernetes 1.24+
- kubectl 설정 완료
- Helm 3.0+ (선택사항)
- 최소 8GB RAM, 4 CPU 코어 (클러스터 전체)

### 1. 네임스페이스 생성

```bash
kubectl create namespace production
kubectl create namespace staging
```

### 2. 시크릿 생성

```bash
# 데이터베이스 시크릿
kubectl create secret generic backup-manager-secrets \
  --from-literal=database-url="postgresql://user:pass@host:5432/db" \
  --from-literal=encryption-key="your_32_character_encryption_key" \
  --from-literal=redis-url="redis://redis:6379/0" \
  --from-literal=smtp-user="your-email@gmail.com" \
  --from-literal=smtp-password="your-app-password" \
  --from-literal=slack-webhook-url="https://hooks.slack.com/..." \
  -n production

# TLS 인증서 (Let's Encrypt 또는 자체 서명)
kubectl create secret tls backup-manager-tls \
  --cert=path/to/tls.crt \
  --key=path/to/tls.key \
  -n production
```

### 3. 스토리지 클래스 및 PVC 생성

```bash
# 스토리지 클래스 (AWS EBS 예시)
cat <<EOF | kubectl apply -f -
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: backup-storage
provisioner: ebs.csi.aws.com
parameters:
  type: gp3
  fsType: ext4
allowVolumeExpansion: true
volumeBindingMode: WaitForFirstConsumer
EOF

# PVC 생성
kubectl apply -f k8s/production/pvc.yaml
```

### 4. ConfigMap 및 Secret 적용

```bash
kubectl apply -f k8s/production/configmap.yaml
kubectl apply -f k8s/production/secrets.yaml
```

### 5. 애플리케이션 배포

```bash
# Blue 환경 배포
kubectl apply -f k8s/production/blue/

# 서비스 생성
kubectl apply -f k8s/production/service.yaml

# Ingress 생성
kubectl apply -f k8s/production/ingress.yaml
```

### 6. 배포 확인

```bash
# Pod 상태 확인
kubectl get pods -n production

# 서비스 확인
kubectl get svc -n production

# 로그 확인
kubectl logs -f deployment/backup-manager-app-blue -n production

# 헬스체크
kubectl port-forward svc/backup-manager-service 8080:80 -n production
curl http://localhost:8080/api/health
```

## 클라우드 배포

### AWS ECS/Fargate

#### 1. ECR 리포지토리 생성

```bash
# ECR 리포지토리 생성
aws ecr create-repository --repository-name backup-manager

# Docker 이미지 빌드 및 푸시
docker build -t backup-manager .
docker tag backup-manager:latest 123456789012.dkr.ecr.us-west-2.amazonaws.com/backup-manager:latest
docker push 123456789012.dkr.ecr.us-west-2.amazonaws.com/backup-manager:latest
```

#### 2. ECS 클러스터 생성

```bash
# Fargate 클러스터 생성
aws ecs create-cluster --cluster-name backup-manager-cluster --capacity-providers FARGATE
```

#### 3. 태스크 정의 생성

`ecs-task-definition.json`:

```json
{
  "family": "backup-manager",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::123456789012:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "backup-manager",
      "image": "123456789012.dkr.ecr.us-west-2.amazonaws.com/backup-manager:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "ENVIRONMENT",
          "value": "production"
        }
      ],
      "secrets": [
        {
          "name": "DATABASE_URL",
          "valueFrom": "arn:aws:secretsmanager:us-west-2:123456789012:secret:backup-manager/database-url"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/backup-manager",
          "awslogs-region": "us-west-2",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

#### 4. 서비스 생성

```bash
# 태스크 정의 등록
aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json

# 서비스 생성
aws ecs create-service \
  --cluster backup-manager-cluster \
  --service-name backup-manager-service \
  --task-definition backup-manager:1 \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-12345,subnet-67890],securityGroups=[sg-abcdef],assignPublicIp=ENABLED}"
```

### Google Cloud Run

#### 1. 이미지 빌드 및 푸시

```bash
# Cloud Build를 사용한 이미지 빌드
gcloud builds submit --tag gcr.io/PROJECT_ID/backup-manager

# 또는 로컬에서 빌드
docker build -t gcr.io/PROJECT_ID/backup-manager .
docker push gcr.io/PROJECT_ID/backup-manager
```

#### 2. Cloud Run 서비스 배포

```bash
gcloud run deploy backup-manager \
  --image gcr.io/PROJECT_ID/backup-manager \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars ENVIRONMENT=production \
  --set-secrets DATABASE_URL=backup-manager-db-url:latest \
  --memory 2Gi \
  --cpu 2 \
  --min-instances 1 \
  --max-instances 10
```

## 모니터링 설정

### Prometheus + Grafana

#### 1. Prometheus 설정

`monitoring/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'backup-manager'
    static_configs:
      - targets: ['app:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres:5432']

  - job_name: 'redis'
    static_configs:
      - targets: ['redis:6379']
```

#### 2. Grafana 대시보드

- 백업 성공/실패 비율
- 백업 소요 시간 추이
- 시스템 리소스 사용량
- 데이터베이스 연결 상태

### 로그 수집 (ELK Stack)

#### 1. Filebeat 설정

```yaml
filebeat.inputs:
- type: log
  paths:
    - /app/data/logs/*.log
  fields:
    service: backup-manager
  fields_under_root: true

output.elasticsearch:
  hosts: ["elasticsearch:9200"]

setup.kibana:
  host: "kibana:5601"
```

## 보안 설정

### 1. 네트워크 보안

```bash
# 방화벽 규칙 (iptables 예시)
iptables -A INPUT -p tcp --dport 8000 -s 10.0.0.0/8 -j ACCEPT
iptables -A INPUT -p tcp --dport 8000 -j DROP

# Kubernetes Network Policy
kubectl apply -f k8s/production/network-policy.yaml
```

### 2. 인증서 관리

```bash
# Let's Encrypt 인증서 자동 갱신
certbot certonly --webroot -w /var/www/html -d backup-manager.example.com

# 인증서 갱신 크론잡
0 2 * * * certbot renew --quiet
```

### 3. 시크릿 관리

```bash
# Kubernetes Secrets 암호화
kubectl create secret generic backup-manager-secrets \
  --from-literal=api-key="$(openssl rand -base64 32)" \
  --dry-run=client -o yaml | kubectl apply -f -

# AWS Secrets Manager 사용
aws secretsmanager create-secret \
  --name backup-manager/database-url \
  --secret-string "postgresql://user:pass@host:5432/db"
```

## 백업 및 복구

### 1. 애플리케이션 데이터 백업

```bash
# 데이터베이스 백업
docker-compose exec postgres pg_dump -U backup_user backup_manager > backup_$(date +%Y%m%d).sql

# 백업 파일 백업
tar -czf backup_files_$(date +%Y%m%d).tar.gz data/backups/

# S3에 업로드
aws s3 cp backup_files_$(date +%Y%m%d).tar.gz s3://backup-manager-backups/
```

### 2. 복구 절차

```bash
# 데이터베이스 복구
docker-compose exec postgres psql -U backup_user -d backup_manager < backup_20240101.sql

# 백업 파일 복구
tar -xzf backup_files_20240101.tar.gz -C data/

# 서비스 재시작
docker-compose restart app
```

## 트러블슈팅

### 일반적인 문제

#### 1. 컨테이너 시작 실패

```bash
# 로그 확인
docker-compose logs app

# 컨테이너 내부 접근
docker-compose exec app bash

# 설정 확인
docker-compose exec app cat /app/config/settings.yaml
```

#### 2. 데이터베이스 연결 실패

```bash
# 연결 테스트
docker-compose exec app python -c "
from app.database import engine
try:
    engine.connect()
    print('Database connection successful')
except Exception as e:
    print(f'Database connection failed: {e}')
"
```

#### 3. 백업 실패

```bash
# pg_dump 버전 확인
docker-compose exec app pg_dump --version

# 권한 확인
docker-compose exec app ls -la /app/data/backups/

# 디스크 공간 확인
docker-compose exec app df -h
```

### 성능 최적화

#### 1. 리소스 모니터링

```bash
# 컨테이너 리소스 사용량
docker stats

# 시스템 리소스
htop
iotop
```

#### 2. 데이터베이스 최적화

```sql
-- 인덱스 사용량 확인
SELECT schemaname, tablename, attname, n_distinct, correlation
FROM pg_stats
WHERE tablename = 'backups';

-- 쿼리 성능 분석
EXPLAIN ANALYZE SELECT * FROM backups WHERE status = 'completed';
```

## 업데이트 및 롤백

### 1. 무중단 업데이트

```bash
# Blue-Green 배포 (Kubernetes)
kubectl set image deployment/backup-manager-app-blue backup-manager=backup-manager:v1.1.0 -n production
kubectl rollout status deployment/backup-manager-app-blue -n production

# 트래픽 전환
kubectl patch service backup-manager-service -p '{"spec":{"selector":{"version":"blue"}}}' -n production
```

### 2. 롤백

```bash
# Kubernetes 롤백
kubectl rollout undo deployment/backup-manager-app-blue -n production

# Docker Compose 롤백
docker-compose down
git checkout v1.0.0
docker-compose up -d
```

## 운영 체크리스트

### 배포 전 확인사항

- [ ] 환경 변수 설정 완료
- [ ] 시크릿 생성 완료
- [ ] 스토리지 준비 완료
- [ ] 네트워크 설정 완료
- [ ] 모니터링 설정 완료
- [ ] 백업 전략 수립 완료

### 배포 후 확인사항

- [ ] 헬스체크 통과
- [ ] 로그 정상 출력
- [ ] 데이터베이스 연결 정상
- [ ] 백업 기능 테스트
- [ ] 알림 기능 테스트
- [ ] 모니터링 대시보드 확인

### 정기 점검사항

- [ ] 디스크 공간 확인
- [ ] 백업 파일 정리
- [ ] 로그 로테이션 확인
- [ ] 보안 업데이트 적용
- [ ] 성능 지표 검토
- [ ] 인증서 만료일 확인

## 지원 및 문의

- 문서: [https://docs.backup-manager.example.com](https://docs.backup-manager.example.com)
- 이슈 트래커: [https://github.com/your-org/backup-manager/issues](https://github.com/your-org/backup-manager/issues)
- 이메일: support@backup-manager.example.com
- Slack: #backup-manager-support
