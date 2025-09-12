"""
클라우드 데이터베이스 백업 시스템 메인 애플리케이션
FastAPI 기반 REST API 서버
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from fastapi.templating import Jinja2Templates
import uvicorn
import logging
from pathlib import Path

from app.config import settings
from app.database import init_database
from app.api import databases, backups, schedules, monitoring
from app.core.database_manager import db_manager

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
templates = Jinja2Templates(directory="web/templates")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    # 시작 시 초기화
    logger.info("클라우드 데이터베이스 백업 시스템 시작 중...")
    
    # 데이터베이스 초기화
    await init_database()
    
    # 필요한 디렉토리 생성
    Path("data/backups").mkdir(parents=True, exist_ok=True)
    Path("data/logs").mkdir(parents=True, exist_ok=True)
    Path("data/temp").mkdir(parents=True, exist_ok=True)
    Path("data/reports").mkdir(parents=True, exist_ok=True)
    Path("web/static").mkdir(parents=True, exist_ok=True)
    Path("web/templates").mkdir(parents=True, exist_ok=True)
    Path("web/static/js").mkdir(parents=True, exist_ok=True)
    
    logger.info("시스템 초기화 완료")
    
    yield
    
    # 종료 시 정리
    logger.info("클라우드 데이터베이스 백업 시스템 종료 중...")
    # 연결 풀 정리
    try:
        db_manager.close_all()
        logger.info("데이터베이스 연결 풀 정리 완료")
    except Exception as e:
        logger.error(f"연결 풀 정리 중 오류: {e}")

# FastAPI 앱 초기화
app = FastAPI(
    title="클라우드 데이터베이스 백업 관리 시스템",
    description="클라우드 데이터베이스 데이터베이스 자동 백업 시스템",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 신뢰할 수 있는 호스트 미들웨어
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # 프로덕션에서는 특정 호스트로 제한
)

# 정적 파일 서빙
app.mount("/static", StaticFiles(directory="web/static"), name="static")
app.mount("/static/reports", StaticFiles(directory="data/reports", check_dir=False), name="reports")

# API 라우터 등록
app.include_router(databases.router, prefix="/api/databases", tags=["databases"])
app.include_router(backups.router, prefix="/api/backups", tags=["backups"])
app.include_router(schedules.router, prefix="/api/schedules", tags=["schedules"])
app.include_router(monitoring.router, prefix="/api/monitoring", tags=["monitoring"])


@app.get("/", response_class=HTMLResponse)
async def root():
    """루트 엔드포인트 - 웹 인터페이스"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>클라우드 데이터베이스 백업 관리 시스템</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body>
        <div class="container mt-5">
            <div class="row justify-content-center">
                <div class="col-md-8">
                    <div class="card">
                        <div class="card-header bg-primary text-white">
                            <h1 class="card-title mb-0">클라우드 데이터베이스 백업 관리 시스템</h1>
                        </div>
                        <div class="card-body">
                            <p class="card-text">클라우드 데이터베이스 자동 백업 시스템에 오신 것을 환영합니다.</p>
                            <div class="d-grid gap-2">
                                <a href="/api/docs" class="btn btn-primary">API 문서 (Swagger)</a>
                                <a href="/api/redoc" class="btn btn-outline-primary">API 문서 (ReDoc)</a>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """대시보드 HTML 페이지 렌더링"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/databases", response_class=HTMLResponse)
async def databases_page(request: Request):
    """데이터베이스 관리 HTML 페이지 렌더링"""
    return templates.TemplateResponse("databases.html", {"request": request})

@app.get("/backups/{backup_id}", response_class=HTMLResponse)
async def backup_detail_page(request: Request, backup_id: str):
    """백업 상세 HTML 페이지 렌더링"""
    return templates.TemplateResponse("backup_detail.html", {"request": request, "backup_id": backup_id})

@app.get("/databases/{database_id}", response_class=HTMLResponse)
async def database_detail_page(request: Request, database_id: str):
    """데이터베이스 상세 HTML 페이지 렌더링"""
    return templates.TemplateResponse("database_detail.html", {"request": request, "database_id": database_id})

@app.get("/benchmarks", response_class=HTMLResponse)
async def benchmarks_page(request: Request):
    """벤치마크 리포트 업로드/열람 HTML 페이지 렌더링"""
    return templates.TemplateResponse("benchmarks.html", {"request": request})

@app.get("/api/health")
async def health_check():
    """헬스체크 엔드포인트"""
    return {
        "status": "healthy", 
        "service": "Cloud Database Backup Manager",
        "version": "1.0.0"
    }

@app.get("/api/info")
async def system_info():
    """시스템 정보 엔드포인트"""
    return {
        "title": "클라우드 데이터베이스 백업 관리 시스템",
        "description": "클라우드 데이터베이스 자동 백업 시스템",
        "version": "1.0.0",
        "environment": "development" if settings.DEBUG else "production",
        "host": settings.HOST,
        "port": settings.PORT
    }

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )
