"""
간단한 세션 기반 인증 유틸리티
- 외부 의존성 없이 hashlib/hmac 기반 구현
- settings.yaml 의 security 설정을 사용 (enable_auth, admin 계정)

보안 주의:
- 운영 환경에서는 admin 비밀번호 해시/솔트를 환경변수나 외부 비밀 저장소로 관리하는 것을 권장
- 여기서는 settings.yaml(security.admin.*)을 읽어 데모/개발용으로 사용

CRLF 유지, 한국어 주석
"""

from __future__ import annotations
import base64
import hmac
import hashlib
import hmac
import secrets
import re
import time
from typing import Optional, Tuple
from datetime import datetime, timedelta
from fastapi import Request
from app.config import get_config_manager, settings
from app.database import SessionLocal, User

# 세션 쿠키 이름
SESSION_COOKIE_NAME = "lbm_session"
# 세션 기본 만료(초)
DEFAULT_SESSION_TTL = 60 * 60 * 8  # 8시간


def _get_security_conf() -> dict:
    """settings.yaml 의 security 섹션 반환 (기본값 병합)"""
    cm = get_config_manager()
    data = cm.load_app_settings() or {}
    sec = (data.get("security") or {})
    admin = (sec.get("admin") or {})
    return {
        "enable_auth": bool(sec.get("enable_auth", False)),
        "admin_username": str(admin.get("username") or "admin"),
        # 비밀번호는 pbkdf2_hmac 기반 해시를 기대. 없으면 로그인 불가 처리.
        "admin_password_hash": str(admin.get("password_hash") or ""),
        "admin_password_salt": str(admin.get("password_salt") or ""),
        "session_ttl": int(sec.get("session_ttl") or DEFAULT_SESSION_TTL),
    }


def pbkdf2_hash(password: str, salt: str, iterations: int = 100_000) -> str:
    """표준 라이브러리 pbkdf2_hmac으로 해시 생성(Base64)
    - 알고리즘: sha256
    """
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    return base64.b64encode(dk).decode("ascii")


def verify_password(plain: str, salt: str, expected_b64: str) -> bool:
    """비밀번호 검증 (타이밍 공격 방지 위해 hmac.compare_digest 사용)"""
    if not expected_b64 or not salt:
        return False
    calc = pbkdf2_hash(plain, salt)
    return hmac.compare_digest(calc, expected_b64)


def _sign(data: str) -> str:
    """HMAC-SHA256 서명(Base64) - SECRET_KEY 기반"""
    key = (settings.SECRET_KEY or "").encode("utf-8")
    sig = hmac.new(key, data.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(sig).decode("ascii")


def create_session_token(username: str, ttl_seconds: Optional[int] = None) -> str:
    """세션 토큰 생성: base64(username)|exp|base64(signature)
    - signature = HMAC-SHA256(username|exp)
    """
    ttl = int(ttl_seconds or DEFAULT_SESSION_TTL)
    exp = int(time.time()) + ttl
    u = base64.b64encode(username.encode("utf-8")).decode("ascii")
    payload = f"{u}|{exp}"
    sig = _sign(payload)
    return f"{payload}|{sig}"


def verify_session_token(token: str) -> Tuple[bool, Optional[str]]:
    """세션 토큰 검증 -> (유효여부, username)"""
    try:
        parts = token.split("|")
        if len(parts) != 3:
            return False, None
        u_b64, exp_str, sig = parts
        payload = f"{u_b64}|{exp_str}"
        if not hmac.compare_digest(sig, _sign(payload)):
            return False, None
        exp = int(exp_str)
        if time.time() > exp:
            return False, None
        username = base64.b64decode(u_b64.encode("ascii")).decode("utf-8")
        return True, username
    except Exception:
        return False, None


def get_current_user_from_request(request: Request) -> Optional[str]:
    """요청의 쿠키에서 현재 사용자 추출 (검증 포함)"""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    ok, username = verify_session_token(token)
    return username if ok else None


def is_auth_enabled() -> bool:
    return _get_security_conf().get("enable_auth", False)


def _validate_admin_credentials_from_settings(username: str, password: str) -> bool:
    """설정(settings.yaml) 기반 admin 계정 검증 (레거시/백업 경로)"""
    sec = _get_security_conf()
    if not sec.get("admin_password_hash") or not sec.get("admin_password_salt"):
        return False
    if username != sec.get("admin_username"):
        return False
    return verify_password(password, sec.get("admin_password_salt"), sec.get("admin_password_hash"))


def db_has_any_user() -> bool:
    """DB에 사용자 레코드가 하나라도 존재하는지 확인"""
    db = SessionLocal()
    try:
        return db.query(User).first() is not None
    finally:
        db.close()


def validate_user_credentials(username: str, password: str) -> bool:
    """DB 기반 사용자 검증 (우선)
    - users 테이블에 사용자가 없을 경우에만 settings 기반 admin 검증을 폴백으로 허용
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username, User.is_active == True).first()
        if user:
            return verify_password(password, user.password_salt, user.password_hash)
    finally:
        db.close()
    # DB에 유저가 없으면 설정 기반 admin을 폴백으로 허용(초기 부트스트랩 시나리오)
    return _validate_admin_credentials_from_settings(username, password)


# ===== 역할 기반 접근 제어(RBAC) 유틸 =====
def get_user_role(username: str) -> Optional[str]:
    """사용자의 역할(role) 조회
    - DB에서 조회하며 사용자가 없으면 None
    """
    if not username:
        return None
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return None
        return user.role
    finally:
        db.close()


def user_has_role(username: str, allowed_roles: Tuple[str, ...]) -> bool:
    """사용자가 허용된 역할 중 하나를 가지는지 검사"""
    role = get_user_role(username)
    if role is None:
        return False
    return role in allowed_roles


def require_roles(request: Request, allowed_roles: Tuple[str, ...]) -> bool:
    """요청 쿠키 기반 사용자 역할을 검사하여 접근 허용 여부 반환
    - 미인증 또는 권한 부족 시 False
    """
    user = get_current_user_from_request(request)
    if not user:
        return False
    return user_has_role(user, allowed_roles)


# ===== 비밀번호 정책 강화 =====
def validate_password_policy(password: str) -> Tuple[bool, list[str]]:
    """비밀번호 정책 검증
    반환: (유효여부, 오류메시지 리스트)
    """
    errors = []
    
    # 최소 길이 검사 (8자 이상)
    if len(password) < 8:
        errors.append("비밀번호는 최소 8자 이상이어야 합니다.")
    
    # 최대 길이 검사 (128자 이하)
    if len(password) > 128:
        errors.append("비밀번호는 최대 128자 이하여야 합니다.")
    
    # 복잡도 검사
    has_upper = bool(re.search(r'[A-Z]', password))
    has_lower = bool(re.search(r'[a-z]', password))
    has_digit = bool(re.search(r'\d', password))
    has_special = bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', password))
    
    complexity_count = sum([has_upper, has_lower, has_digit, has_special])
    if complexity_count < 3:
        errors.append("비밀번호는 대문자, 소문자, 숫자, 특수문자 중 최소 3가지를 포함해야 합니다.")
    
    # 연속 문자 검사 (3자 이상 연속 금지)
    for i in range(len(password) - 2):
        if password[i] == password[i+1] == password[i+2]:
            errors.append("동일한 문자가 3번 이상 연속으로 사용될 수 없습니다.")
            break
    
    # 일반적인 패턴 검사
    common_patterns = ['123', 'abc', 'password', 'admin', 'qwerty']
    password_lower = password.lower()
    for pattern in common_patterns:
        if pattern in password_lower:
            errors.append(f"일반적인 패턴 '{pattern}'은 사용할 수 없습니다.")
            break
    
    return len(errors) == 0, errors


def is_password_expired(user_id: str) -> bool:
    """비밀번호 만료 여부 확인 (90일 기준)"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not hasattr(user, 'password_changed_at'):
            return False
        
        if user.password_changed_at is None:
            return True  # 변경 이력이 없으면 만료로 간주
        
        # 90일 만료 정책
        expiry_date = user.password_changed_at + timedelta(days=90)
        return datetime.utcnow() > expiry_date
    finally:
        db.close()


def check_password_reuse(username: str, new_password: str, history_count: int = 5) -> bool:
    """최근 사용한 비밀번호 재사용 검사
    반환: True면 재사용(금지), False면 사용 가능
    """
    # 실제 구현에서는 password_history 테이블이 필요하지만
    # 현재 스키마에는 없으므로 기본 구현만 제공
    # TODO: password_history 테이블 추가 후 구현
    return False


def generate_secure_password(length: int = 12) -> str:
    """보안 정책을 만족하는 임시 비밀번호 생성"""
    import string
    
    # 각 카테고리에서 최소 1개씩 선택
    upper = secrets.choice(string.ascii_uppercase)
    lower = secrets.choice(string.ascii_lowercase)
    digit = secrets.choice(string.digits)
    special = secrets.choice('!@#$%^&*')
    
    # 나머지 길이만큼 랜덤 선택
    all_chars = string.ascii_letters + string.digits + '!@#$%^&*'
    remaining = ''.join(secrets.choice(all_chars) for _ in range(length - 4))
    
    # 섞어서 반환
    password_chars = list(upper + lower + digit + special + remaining)
    secrets.SystemRandom().shuffle(password_chars)
    
    return ''.join(password_chars)


# ===== 세션 보안 강화 =====
# 활성 세션 추적을 위한 메모리 저장소 (실제 운영에서는 Redis 등 사용 권장)
_active_sessions: Dict[str, Dict[str, any]] = {}
_user_sessions: Dict[str, set] = {}  # username -> set of session_ids

def create_secure_session_token(username: str, request: Request, ttl_seconds: Optional[int] = None) -> Tuple[str, str]:
    """보안 강화된 세션 토큰 생성
    반환: (session_token, session_id)
    """
    # 기본 세션 토큰 생성
    session_token = create_session_token(username, ttl_seconds)
    
    # 세션 ID 생성 (추적용)
    session_id = secrets.token_urlsafe(32)
    
    # 세션 정보 저장
    session_info = {
        'username': username,
        'created_at': datetime.utcnow(),
        'last_activity': datetime.utcnow(),
        'ip_address': request.client.host if request.client else None,
        'user_agent': request.headers.get('user-agent', ''),
        'session_token': session_token
    }
    
    _active_sessions[session_id] = session_info
    
    # 사용자별 세션 추적
    if username not in _user_sessions:
        _user_sessions[username] = set()
    _user_sessions[username].add(session_id)
    
    # 동시 로그인 제한 (최대 3개 세션)
    if len(_user_sessions[username]) > 3:
        # 가장 오래된 세션 제거
        oldest_session = min(
            _user_sessions[username],
            key=lambda sid: _active_sessions.get(sid, {}).get('created_at', datetime.utcnow())
        )
        invalidate_session(oldest_session)
    
    return session_token, session_id


def validate_secure_session_token(token: str, request: Request) -> Tuple[bool, Optional[str], Optional[str]]:
    """보안 강화된 세션 토큰 검증
    반환: (유효여부, username, session_id)
    """
    # 기본 토큰 검증
    is_valid, username = verify_session_token(token)
    if not is_valid or not username:
        return False, None, None
    
    # 활성 세션에서 찾기
    session_id = None
    for sid, info in _active_sessions.items():
        if info.get('session_token') == token and info.get('username') == username:
            session_id = sid
            break
    
    if not session_id:
        return False, None, None
    
    session_info = _active_sessions[session_id]
    
    # 세션 고정 공격 방지 - IP 주소 검증 (선택적)
    current_ip = request.client.host if request.client else None
    stored_ip = session_info.get('ip_address')
    if stored_ip and current_ip and stored_ip != current_ip:
        # IP 변경 시 세션 무효화 (엄격한 정책)
        invalidate_session(session_id)
        return False, None, None
    
    # 비활성 타임아웃 검사 (30분)
    last_activity = session_info.get('last_activity')
    if last_activity and datetime.utcnow() - last_activity > timedelta(minutes=30):
        invalidate_session(session_id)
        return False, None, None
    
    # 활동 시간 업데이트
    session_info['last_activity'] = datetime.utcnow()
    
    return True, username, session_id


def invalidate_session(session_id: str):
    """세션 무효화"""
    if session_id in _active_sessions:
        session_info = _active_sessions[session_id]
        username = session_info.get('username')
        
        # 활성 세션에서 제거
        del _active_sessions[session_id]
        
        # 사용자 세션 목록에서 제거
        if username and username in _user_sessions:
            _user_sessions[username].discard(session_id)
            if not _user_sessions[username]:
                del _user_sessions[username]


def invalidate_all_user_sessions(username: str):
    """특정 사용자의 모든 세션 무효화"""
    if username in _user_sessions:
        session_ids = list(_user_sessions[username])
        for session_id in session_ids:
            invalidate_session(session_id)


def get_user_active_sessions(username: str) -> List[Dict[str, any]]:
    """사용자의 활성 세션 목록 조회"""
    if username not in _user_sessions:
        return []
    
    sessions = []
    for session_id in _user_sessions[username]:
        if session_id in _active_sessions:
            info = _active_sessions[session_id].copy()
            # 민감한 정보 제거
            info.pop('session_token', None)
            info['session_id'] = session_id
            sessions.append(info)
    
    return sessions


def cleanup_expired_sessions():
    """만료된 세션 정리 (주기적 실행 권장)"""
    current_time = datetime.utcnow()
    expired_sessions = []
    
    for session_id, info in _active_sessions.items():
        # 토큰 만료 검사
        token = info.get('session_token', '')
        is_valid, _ = verify_session_token(token)
        if not is_valid:
            expired_sessions.append(session_id)
            continue
        
        # 비활성 타임아웃 검사
        last_activity = info.get('last_activity')
        if last_activity and current_time - last_activity > timedelta(minutes=30):
            expired_sessions.append(session_id)
    
    for session_id in expired_sessions:
        invalidate_session(session_id)
