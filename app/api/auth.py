"""
인증 API
- 로그인 페이지 렌더링(GET /login)
- 로그인 처리(POST /api/auth/login)
- 로그아웃 처리(POST /api/auth/logout)

외부 의존성 추가 없이 세션 쿠키 기반으로 동작
한글 주석, CRLF 유지
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Dict
import logging

from app.core.auth import (
    validate_user_credentials,
    create_session_token,
    SESSION_COOKIE_NAME,
    is_auth_enabled,
)
from app.core.auth import get_current_user_from_request, db_has_any_user, pbkdf2_hash
from app.database import SessionLocal, User
import os, base64

templates = Jinja2Templates(directory="web/templates")
logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_page(request: Request):
    """로그인 폼 페이지 렌더링"""
    if not is_auth_enabled():
        # 인증 비활성화 시 바로 대시보드로
        return templates.TemplateResponse("dashboard.html", {"request": request})
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/api/auth/login")
async def login(request: Request, payload: Dict[str, str]):
    """로그인 처리: 성공 시 세션 쿠키 설정"""
    if not is_auth_enabled():
        raise HTTPException(status_code=400, detail="인증이 비활성화되어 있습니다.")
    username = (payload or {}).get("username", "").strip()
    password = (payload or {}).get("password", "")
    if not username or not password:
        raise HTTPException(status_code=400, detail="아이디/비밀번호를 입력하세요.")
    if not validate_user_credentials(username, password):
        raise HTTPException(status_code=401, detail="로그인 실패")

    token = create_session_token(username)
    res = JSONResponse({"message": "ok"})
    # HTTPS 환경에서는 secure=True 권장
    secure = (request.headers.get("x-forwarded-proto", request.url.scheme).lower() == "https")
    res.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    return res


@router.post("/api/auth/logout")
async def logout(request: Request):
    """로그아웃: 세션 쿠키 제거"""
    res = JSONResponse({"message": "ok"})
    res.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return res


@router.get("/api/auth/me")
async def auth_me(request: Request):
    """현재 로그인 사용자 조회"""
    user = get_current_user_from_request(request)
    return {"user": user}


@router.post("/api/auth/bootstrap-user")
async def bootstrap_user(payload: Dict[str, str]):
    """초기 사용자 생성(최초 1회)
    - users 테이블이 비어있는 경우에만 허용
    - 입력: username, password, full_name(optional), role(optional)
    """
    if not is_auth_enabled():
        raise HTTPException(status_code=400, detail="인증이 비활성화되어 있습니다.")
    if db_has_any_user():
        raise HTTPException(status_code=400, detail="이미 사용자가 존재합니다.")
    username = (payload or {}).get("username", "").strip()
    password = (payload or {}).get("password", "")
    full_name = (payload or {}).get("full_name")
    role = (payload or {}).get("role") or "admin"
    if not username or not password:
        raise HTTPException(status_code=400, detail="username/password가 필요합니다.")
    # 솔트 생성(Base64)
    salt = base64.b64encode(os.urandom(16)).decode("ascii")
    hash_b64 = pbkdf2_hash(password, salt)
    db = SessionLocal()
    try:
        # 중복 사용자 방지
        if db.query(User).filter(User.username == username).first():
            raise HTTPException(status_code=400, detail="이미 존재하는 사용자입니다.")
        u = User(username=username, full_name=full_name, password_hash=hash_b64, password_salt=salt, role=role, is_active=True)
        db.add(u)
        db.commit()
        db.refresh(u)
        return {"message": "created", "id": u.id, "username": u.username}
    finally:
        db.close()
