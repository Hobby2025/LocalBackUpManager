"""
클라우드 데이터베이스 백업 시스템 메인 애플리케이션
FastAPI 기반 REST API 서버
"""

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from fastapi.templating import Jinja2Templates
import uvicorn
import logging
from pathlib import Path
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.database import init_database
from app.api import databases, backups, schedules, monitoring
from app.api import notifications
from app.api import settings as settings_api
from app.api import app_settings as app_settings_api
from app.api import auth as auth_api
from app.api import audit
from app.core.database_manager import db_manager
from app.core.audit_middleware import AuditMiddleware, AuditActionMiddleware

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data/logs/app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# HTTPS 강제 및 HSTS 헤더 추가 미들웨어 (설정 토글 기반)
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """보안 관련 헤더 및 HTTPS 강제 처리
    - 프록시(Load Balancer) 뒤에서 X-Forwarded-Proto 헤더를 신뢰하는 환경을 가정
    - 개발 환경(settings.DEBUG=True)에서는 HTTPS 리다이렉트를 강제하지 않음
    """
    async def dispatch(self, request: Request, call_next):
        # settings.yaml의 security 섹션 읽기 (간단 로딩)
        from app.config import get_config_manager
        cm = get_config_manager()
        app_settings = cm.load_app_settings() or {}
        sec = (app_settings.get('security') or {})
        enable_redirect = bool(sec.get('enable_https_redirect'))
        enable_hsts = bool(sec.get('enable_hsts'))

        # HTTPS 리다이렉트 (프록시가 전달한 X-Forwarded-Proto 기반)
        try:
            if enable_redirect and not settings.DEBUG:
                xf_proto = request.headers.get('x-forwarded-proto') or request.headers.get('X-Forwarded-Proto')
                if xf_proto and xf_proto.lower() != 'https':
                    url = request.url.replace(scheme='https')
                    return Response(status_code=307, headers={'Location': str(url)})
        except Exception:
            pass

        response = await call_next(request)
        # 보안 헤더
        try:
            if enable_hsts:
                response.headers['Strict-Transport-Security'] = 'max-age=63072000; includeSubDomains; preload'
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['Referrer-Policy'] = 'no-referrer'
        except Exception:
            pass
        return response

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="web/templates")

# 인증 강제 미들웨어 (설정 기반)
class AuthMiddleware(BaseHTTPMiddleware):
    """security.enable_auth 가 true일 때 인증을 강제
    - 허용 경로: /login, /api/auth/*, /static/*, /static/reports/*, /api/health, /api/openapi.json, /api/docs, /api/redoc
    - 인증 실패 시: HTML 경로는 /login 리다이렉트, API 경로는 401 JSON
    """
    async def dispatch(self, request: Request, call_next):
        from app.core.auth import is_auth_enabled, get_current_user_from_request
        if not is_auth_enabled():
            return await call_next(request)
        path = request.url.path or "/"
        allow_prefixes = (
            "/login",
            "/api/auth/",
            "/static/",
            "/api/health",
            "/api/openapi.json",
            "/api/docs",
            "/api/redoc",
        )
        if path == "/":
            # 루트('/') 접근 시 인증 필요하면 /login으로 유도
            from app.core.auth import get_current_user_from_request
            user = get_current_user_from_request(request)
            if user:
                return await call_next(request)
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url="/login", status_code=307)
        if any(path.startswith(p) for p in allow_prefixes):
            return await call_next(request)
        user = get_current_user_from_request(request)
        if user:
            return await call_next(request)
        # 비인증 요청 처리
        if path.startswith("/api/"):
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "인증 필요"}, status_code=401)
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/login", status_code=307)

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
    
    # 암호화 키 검증 (운영 안전성 향상)
    try:
        if getattr(settings, 'DEFAULT_ENCRYPTION', False):
            # settings.yaml 기반 security.encryption(active_key_id, keys) 검증
            from app.config import get_config_manager
            cm = get_config_manager()
            app_settings = cm.load_app_settings() or {}
            sec = (app_settings.get('security') or {})
            enc = (sec.get('encryption') or {})
            active_id = (enc.get('active_key_id') or '').strip()
            keys = enc.get('keys') or []
            valid = False
            if active_id and isinstance(keys, list):
                for item in keys:
                    try:
                        if (item or {}).get('id') == active_id:
                            k = (item or {}).get('key')
                            if isinstance(k, str) and len(k) == 32:
                                valid = True
                                break
                    except Exception:
                        continue
            if not valid:
                logger.error("security.encryption 설정이 올바르지 않거나 활성 키가 32자가 아닙니다. 암호화를 비활성화합니다.")
                try:
                    settings.DEFAULT_ENCRYPTION = False  # 런타임 폴백
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"암호화 키 검증 중 경고: {e}")

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

# 보안 미들웨어 등록 (앱 초기화 이후)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(AuthMiddleware)

# CORS/TrustedHost 설정을 settings.yaml(security)에서 로딩
def _load_security_web_conf():
    from app.config import get_config_manager
    try:
        cm = get_config_manager()
        data = cm.load_app_settings() or {}
        sec = (data.get('security') or {})
        allowed_hosts = sec.get('allowed_hosts') or []
        cors_origins = sec.get('cors_origins') or []
        # 비어있으면 와일드카드 처리
        if not isinstance(allowed_hosts, list):
            allowed_hosts = []
        if not isinstance(cors_origins, list):
            cors_origins = []
        return allowed_hosts, cors_origins
    except Exception:
        return [], []

_allowed_hosts, _cors_origins = _load_security_web_conf()

# CORS 미들웨어 설정 (비어있으면 '*')
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins if _cors_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 신뢰할 수 있는 호스트 미들웨어 (비어있으면 '*')
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=_allowed_hosts if _allowed_hosts else ["*"]
)

# 감사 로깅 미들웨어 추가
app.add_middleware(AuditMiddleware)
app.add_middleware(AuditActionMiddleware)

# 정적 파일 서빙
# 주의: 보다 구체적인 경로(/static/reports)를 먼저 마운트해야 /static에 가려지지 않습니다.
app.mount("/static/reports", StaticFiles(directory="data/reports", check_dir=False), name="reports")
app.mount("/static", StaticFiles(directory="web/static"), name="static")

# API 라우터 등록
app.include_router(auth_api.router)
app.include_router(databases.router, prefix="/api/databases", tags=["databases"])
app.include_router(backups.router, prefix="/api/backups", tags=["backups"])
app.include_router(schedules.router, prefix="/api/schedules", tags=["schedules"])
app.include_router(monitoring.router, prefix="/api/monitoring", tags=["monitoring"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
app.include_router(settings_api.router, prefix="/api/notifications/settings", tags=["settings"])
app.include_router(app_settings_api.router, prefix="/api/app-settings", tags=["app-settings"])
app.include_router(audit.router, tags=["audit"])

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """대시보드 HTML 페이지 렌더링"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/databases", response_class=HTMLResponse)
async def databases_page(request: Request):
    """데이터베이스 관리 HTML 페이지 렌더링"""
    return templates.TemplateResponse("databases.html", {"request": request})

@app.get("/audit", response_class=HTMLResponse)
async def audit_page(request: Request):
    """감사 로그 HTML 페이지 렌더링"""
    return templates.TemplateResponse("audit.html", {"request": request})

@app.get("/security", response_class=HTMLResponse)
async def security_page(request: Request):
    """보안 이벤트 HTML 페이지 렌더링"""
    return templates.TemplateResponse("security.html", {"request": request})

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

@app.get("/notifications", response_class=HTMLResponse)
async def notifications_page(request: Request):
    """알림 이력/테스트 HTML 페이지 렌더링"""
    return templates.TemplateResponse("notifications.html", {"request": request})

@app.get("/settings/notifications", response_class=HTMLResponse)
async def notifications_settings_page(request: Request):
    """알림 설정 HTML 페이지 렌더링"""
    return templates.TemplateResponse("settings_notifications.html", {"request": request})

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
