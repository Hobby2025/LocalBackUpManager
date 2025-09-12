"""
설정 API (Phase 5.1)
- notifications 설정 조회/갱신
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import logging

from app.config import get_config_manager

logger = logging.getLogger(__name__)
router = APIRouter()

SETTINGS_FILE = "settings.yaml"

@router.get("/", summary="알림 설정 조회")
async def get_notifications_settings():
    try:
        cm = get_config_manager()
        data = cm.load_app_settings() or {}
        return {"notifications": data.get("notifications", {})}
    except Exception as e:
        logger.error(f"알림 설정 조회 오류: {e}")
        raise HTTPException(status_code=500, detail="알림 설정 조회 중 오류")

@router.put("/", summary="알림 설정 갱신")
async def update_notifications_settings(payload: Dict[str, Any]):
    """알림 설정 갱신
    - payload 형식: {"notifications": { ... }}
    - 전체 notifications 블록을 교체(부분 변경은 프런트에서 병합 처리 권장)
    """
    try:
        if not isinstance(payload, dict) or "notifications" not in payload:
            raise HTTPException(status_code=400, detail="notifications 키가 필요합니다.")
        cm = get_config_manager()
        data = cm.load_app_settings() or {}
        data["notifications"] = payload["notifications"] or {}
        ok = cm.save_yaml_config(SETTINGS_FILE, data)
        if not ok:
            raise HTTPException(status_code=500, detail="설정 저장 실패")
        return {"message": "저장 완료", "notifications": data["notifications"]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"알림 설정 갱신 오류: {e}")
        raise HTTPException(status_code=500, detail="알림 설정 갱신 중 오류")
