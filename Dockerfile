# PostgreSQL 클라우드 데이터베이스 자동 백업 시스템 Dockerfile
FROM python:3.11-slim

# 메타데이터 설정
LABEL maintainer="LocalBackUpManager Team"
LABEL version="1.0.0"
LABEL description="PostgreSQL Cloud Database Automatic Backup System"

# 환경 변수 설정
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 및 필수 패키지 설치
RUN apt-get update && apt-get install -y \
    # PostgreSQL 클라이언트 도구
    postgresql-client \
    # 압축 도구
    gzip \
    bzip2 \
    xz-utils \
    # 네트워크 도구
    curl \
    wget \
    # 시스템 도구
    procps \
    htop \
    # 빌드 도구 (일부 Python 패키지 컴파일용)
    gcc \
    g++ \
    make \
    # SSL/TLS 지원
    ca-certificates \
    # 정리
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 파일 복사
COPY requirements.txt .

# Python 의존성 설치
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# 디렉토리 구조 생성
RUN mkdir -p /app/data/backups \
    /app/data/logs \
    /app/data/reports \
    /app/data/temp \
    && chmod -R 755 /app/data

# 비root 사용자 생성 및 권한 설정
RUN groupadd -r appuser && \
    useradd -r -g appuser -d /app -s /bin/bash appuser && \
    chown -R appuser:appuser /app

# 헬스체크 스크립트 생성
RUN echo '#!/bin/bash\ncurl -f http://localhost:8000/api/health || exit 1' > /app/healthcheck.sh && \
    chmod +x /app/healthcheck.sh

# 포트 노출
EXPOSE 8000

# 헬스체크 설정
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD /app/healthcheck.sh

# 사용자 변경
USER appuser

# 시작 명령어
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
