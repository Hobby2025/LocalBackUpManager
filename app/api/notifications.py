"""
알림 API 라우터 (Phase 5.1)
- 테스트 전송, 브로드캐스트 전송 제공
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from datetime import datetime
import logging

from app.database import get_db, Notification
from app.core.notification_service import NotificationService

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/", summary="알림 이력 조회")
async def list_notifications(
    skip: int = 0,
    limit: int = 50,
    level: Optional[str] = None,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """알림 이력을 조회합니다."""
    try:
        query = db.query(Notification)
        if level:
            query = query.filter(Notification.level == level)
        if status_filter:
            query = query.filter(Notification.status == status_filter)
        rows = query.order_by(Notification.created_at.desc()).offset(skip).limit(limit).all()
        total = query.count()
        def _ser(n: Notification):
            return {
                "id": n.id,
                "database_id": n.database_id,
                "backup_id": n.backup_id,
                "notification_type": n.notification_type,
                "level": n.level,
                "title": n.title,
                "message": n.message,
                "recipient": n.recipient,
                "status": n.status,
                "sent_at": n.sent_at.isoformat() if n.sent_at else None,
                "error_message": n.error_message,
                "created_at": n.created_at.isoformat() if getattr(n, 'created_at', None) else None,
            }
        return {"total": total, "notifications": [_ser(n) for n in rows]}
    except Exception as e:
        logger.error(f"알림 이력 조회 오류: {e}")
        raise HTTPException(status_code=500, detail="알림 이력 조회 중 오류")


@router.post("/test", summary="알림 테스트 전송")
async def send_test_notification(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    """단일 채널 테스트 전송
    payload 예시: {"channel": "email|slack|discord", "title": "제목", "message": "내용", "to": ["user@example.com"]}
    - channel 미지정 시 email 우선 시도 → slack → discord 순으로 활성 채널 중 첫번째 사용
    """
    try:
        svc = NotificationService()
        ch = (payload.get("channel") or "").lower().strip()
        title = payload.get("title") or "테스트 알림"
        message = payload.get("message") or "테스트 메시지"
        to_list = payload.get("to") or None

        # 채널 결정
        enabled = svc.channels_enabled()
        if not ch:
            ch = "email" if enabled.get("email") else ("slack" if enabled.get("slack") else ("discord" if enabled.get("discord") else ""))
        if not ch:
            raise HTTPException(status_code=400, detail="활성화된 채널이 없습니다. settings.yaml을 확인하세요.")

        # Notification 레코드 생성
        rec = Notification(
            database_id=None,
            backup_id=None,
            notification_type=ch,
            level="info",
            title=title,
            message=message,
            recipient=",".join(to_list) if to_list else None,
            status="pending",
            created_at=datetime.utcnow(),
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)

        # 전송
        if ch == "email":
            result = svc.send_email(subject=title, message=message, to_list=to_list)
        elif ch == "slack":
            result = svc.send_slack(text=f"{title}\n{message}")
        elif ch == "discord":
            result = svc.send_discord(content=f"**{title}**\n{message}")
        else:
            raise HTTPException(status_code=400, detail="지원하지 않는 채널입니다.")

        # 결과 반영
        if result.get("status") == "success":
            rec.status = "sent"
            rec.sent_at = datetime.utcnow()
        else:
            rec.status = "failed"
            rec.error_message = result.get("detail")
        db.commit()

        return {"notification_id": rec.id, "result": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"알림 테스트 전송 오류: {e}")
        raise HTTPException(status_code=500, detail="알림 테스트 전송 중 오류")


@router.post("/broadcast", summary="활성 채널 브로드캐스트")
async def broadcast_notification(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    """활성화된 모든 채널로 동일한 제목/메시지 전송
    payload 예시: {"title": "제목", "message": "내용"}
    """
    try:
        svc = NotificationService()
        title = payload.get("title") or "알림"
        message = payload.get("message") or "메시지"

        # 채널별 Notification 레코드 준비
        enabled = svc.channels_enabled()
        channels = [k for k, v in enabled.items() if v]
        if not channels:
            raise HTTPException(status_code=400, detail="활성화된 채널이 없습니다.")

        rec_map = {}
        for ch in channels:
            rec = Notification(
                database_id=None,
                backup_id=None,
                notification_type=ch,
                level="info",
                title=title,
                message=message,
                status="pending",
                created_at=datetime.utcnow(),
            )
            db.add(rec)
            db.flush()  # id 확보
            rec_map[ch] = rec
        db.commit()

        # 전송 및 업데이트
        results = {}
        for ch, rec in rec_map.items():
            if ch == "email":
                res = svc.send_email(subject=title, message=message)
            elif ch == "slack":
                res = svc.send_slack(text=f"{title}\n{message}")
            elif ch == "discord":
                res = svc.send_discord(content=f"**{title}**\n{message}")
            else:
                res = {"status": "error", "detail": "지원하지 않는 채널"}

            results[ch] = res
            if res.get("status") == "success":
                rec.status = "sent"
                rec.sent_at = datetime.utcnow()
            else:
                rec.status = "failed"
                rec.error_message = res.get("detail")
        db.commit()

        return {"results": results}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"브로드캐스트 전송 오류: {e}")
        raise HTTPException(status_code=500, detail="브로드캐스트 전송 중 오류")


@router.get("/{notification_id}", summary="알림 상세 조회")
async def get_notification_detail(notification_id: str, db: Session = Depends(get_db)):
    """단일 알림 이력 상세 조회"""
    try:
        n = db.query(Notification).filter(Notification.id == notification_id).first()
        if not n:
            raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다.")
        return {
            "id": n.id,
            "database_id": n.database_id,
            "backup_id": n.backup_id,
            "notification_type": n.notification_type,
            "level": n.level,
            "title": n.title,
            "message": n.message,
            "recipient": n.recipient,
            "status": n.status,
            "sent_at": n.sent_at.isoformat() if n.sent_at else None,
            "error_message": n.error_message,
            "created_at": n.created_at.isoformat() if getattr(n, 'created_at', None) else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"알림 상세 조회 오류: {e}")
        raise HTTPException(status_code=500, detail="알림 상세 조회 중 오류")


@router.post("/{notification_id}/resend", summary="알림 재전송")
async def resend_notification(notification_id: str, db: Session = Depends(get_db)):
    """기존 알림 이력의 채널/제목/메시지/수신자를 사용해 재전송"""
    try:
        n = db.query(Notification).filter(Notification.id == notification_id).first()
        if not n:
            raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다.")
        svc = NotificationService()
        ch = (n.notification_type or '').lower().strip()
        # 일부 기록은 broadcast로 저장했을 수 있어 채널별 재시도는 email/slack/discord만 처리
        result = {"status": "error", "detail": "지원하지 않는 채널"}
        if ch == 'email':
            to_list = (n.recipient or '').split(',') if n.recipient else None
            result = svc.send_email(subject=n.title or '', message=n.message or '', to_list=to_list)
        elif ch == 'slack':
            result = svc.send_slack(text=f"{n.title or ''}\n{n.message or ''}")
        elif ch == 'discord':
            result = svc.send_discord(content=f"**{n.title or ''}**\n{n.message or ''}")
        else:
            # broadcast의 경우 활성 채널 전체로 송신
            result = svc.broadcast(title=n.title or '', message=n.message or '')
        # 재전송 기록 추가(간단히 새 레코드 생성)
        rec = Notification(
            database_id=n.database_id,
            backup_id=n.backup_id,
            notification_type=ch or 'broadcast',
            level=n.level or 'info',
            title=n.title,
            message=n.message,
            recipient=n.recipient,
            status='sent' if (isinstance(result, dict) and result.get('status') == 'success') or any((v or {}).get('status')=='success' for v in (result.values() if isinstance(result, dict) else [] ) if isinstance(v, dict)) else 'failed',
            created_at=datetime.utcnow(),
        )
        if rec.status == 'sent':
            rec.sent_at = datetime.utcnow()
        else:
            rec.error_message = (result.get('detail') if isinstance(result, dict) else None)
        db.add(rec)
        db.commit()
        return {"resend_id": rec.id, "result": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"알림 재전송 오류: {e}")
        raise HTTPException(status_code=500, detail="알림 재전송 중 오류")
