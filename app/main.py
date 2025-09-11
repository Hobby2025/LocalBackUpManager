"""
PostgreSQL 백업 시스템 메인 애플리케이션
FastAPI 기반 REST API 서버
"""

from fastapi import FastAPI
import uvicorn
import logging
from pathlib import Path

from app.config import settings
from app.database import init_database

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data/logs/app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# FastAPI 앱 초기화
app = FastAPI(
    title="클라우드 데이터베이스 백업 관리 시스템",
    description="클라우드 데이터베이스 데이터베이스 자동 백업 시스템",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 시 초기화"""
    logger.info("PostgreSQL 백업 시스템 시작 중...")
    
    # 데이터베이스 초기화
    await init_database()
    
    # 필요한 디렉토리 생성
    Path("data/backups").mkdir(parents=True, exist_ok=True)
    Path("data/logs").mkdir(parents=True, exist_ok=True)
    
    logger.info("시스템 초기화 완료")

@app.on_event("shutdown")
async def shutdown_event():
    """애플리케이션 종료 시 정리"""
    logger.info("PostgreSQL 백업 시스템 종료 중...")

@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {"message": "PostgreSQL 백업 관리 시스템"}

@app.get("/health")
async def health_check():
    """헬스체크 엔드포인트"""
    return {"status": "healthy", "service": "PostgreSQL Backup Manager"}

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )
