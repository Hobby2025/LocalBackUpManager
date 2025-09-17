"""
애플리케이션 설정 API (일반 설정)
- security 토글 조회/갱신

주의:
- 변수명은 기존 코드와 충돌하지 않게 새로 정의
- 외부 의존성 추가 금지
- 한국어 주석, CRLF
"""

from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any
import logging

from app.config import get_config_manager
from app.core.auth import require_roles

logger = logging.getLogger(__name__)
router = APIRouter()

SETTINGS_FILE = "settings.yaml"


def _load_security(cm) -> Dict[str, Any]:
    """settings.yaml의 security 섹션을 로드하고 기본값과 병합
    기본값:
      enable_https_redirect: False
      enable_hsts: False
      db_ssl_mode_default: "prefer"
    """
    data = cm.load_app_settings() or {}
    sec = (data.get("security") or {})
    return {
        "enable_https_redirect": bool(sec.get("enable_https_redirect", False)),
        "enable_hsts": bool(sec.get("enable_hsts", False)),
        "db_ssl_mode_default": str(sec.get("db_ssl_mode_default", "prefer")),
    }


@router.get("/security", summary="보안 모드 설정 조회")
async def get_security_settings():
    try:
        cm = get_config_manager()
        sec = _load_security(cm)
        return {"security": sec}
    except Exception as e:
        logger.error(f"보안 설정 조회 오류: {e}")
        raise HTTPException(status_code=500, detail="보안 설정 조회 중 오류")


@router.put("/security", summary="보안 모드 설정 갱신")
async def update_security_settings(payload: Dict[str, Any], request: Request):
    """보안 설정 갱신 (admin 권한 필요)
    - payload 형식: {"security": { enable_https_redirect: bool, enable_hsts: bool }}
    - 부분 갱신 허용(주어진 키만 반영)
    """
    # 관리자 권한 검사
    if not require_roles(request, ("admin",)):
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    try:
        if not isinstance(payload, dict) or "security" not in payload:
            raise HTTPException(status_code=400, detail="security 키가 필요합니다.")
        cm = get_config_manager()
        data = cm.load_app_settings() or {}
        current = (data.get("security") or {})
        incoming = payload.get("security") or {}

        # 허용 값만 반영
        result = {
            "enable_https_redirect": bool(incoming.get("enable_https_redirect", current.get("enable_https_redirect", False))),
            "enable_hsts": bool(incoming.get("enable_hsts", current.get("enable_hsts", False))),
            "db_ssl_mode_default": str(incoming.get("db_ssl_mode_default", current.get("db_ssl_mode_default", "prefer"))),
        }

        data["security"] = result
        ok = cm.save_yaml_config(SETTINGS_FILE, data)
        if not ok:
            raise HTTPException(status_code=500, detail="설정 저장 실패")
        return {"message": "저장 완료", "security": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"보안 설정 갱신 오류: {e}")
        raise HTTPException(status_code=500, detail="보안 설정 갱신 중 오류")
