"""
알림 서비스 (Phase 5.1)
- 이메일(SMTP), Slack/Discord 웹훅 지원
- 외부 의존성 없이 표준 라이브러리만 사용
- 설정은 config/settings.yaml 의 notifications 섹션을 사용
"""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List, Dict, Any
import json
import urllib.request

from app.config import get_config_manager, settings


class NotificationService:
    """알림 전송 서비스"""

    def __init__(self):
        self._cfg = self._load_cfg()

    # ---------------------- 설정 로드 ----------------------
    def _load_cfg(self) -> Dict[str, Any]:
        """settings.yaml 의 notifications 섹션 로드"""
        cm = get_config_manager()
        app_settings = cm.load_app_settings() or {}
        return (app_settings.get('notifications') or {})

    def channels_enabled(self) -> Dict[str, bool]:
        ch = (self._cfg.get('channels') or {})
        return {
            'email': bool(ch.get('email')),
            'slack': bool(ch.get('slack')),
            'discord': bool(ch.get('discord')),
        }

    # ---------------------- 전송 메서드 ----------------------
    def send_email(self, subject: str, message: str, to_list: Optional[List[str]] = None) -> Dict[str, Any]:
        """SMTP 이메일 전송 (텍스트)
        - to_list 없으면 설정의 to_addresses 사용
        """
        email_cfg = self._cfg.get('email') or {}
        smtp_host = email_cfg.get('smtp_host')
        smtp_port = int(email_cfg.get('smtp_port') or 587)
        use_tls = bool(email_cfg.get('use_tls'))
        username = email_cfg.get('username') or ''
        password = email_cfg.get('password') or ''
        from_addr = email_cfg.get('from_address') or username or 'noreply@example.com'
        recipients = to_list or (email_cfg.get('to_addresses') or [])

        if not smtp_host or not recipients:
            return { 'status': 'error', 'detail': 'SMTP 호스트 또는 수신자(to_addresses)가 설정되어 있지 않습니다.' }

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = from_addr
        msg['To'] = ', '.join(recipients)
        msg.attach(MIMEText(message, 'plain', 'utf-8'))

        try:
            if use_tls:
                context = ssl.create_default_context()
                with smtplib.SMTP(smtp_host, smtp_port) as server:
                    server.starttls(context=context)
                    if username:
                        server.login(username, password)
                    server.sendmail(from_addr, recipients, msg.as_string())
            else:
                with smtplib.SMTP(smtp_host, smtp_port) as server:
                    if username:
                        server.login(username, password)
                    server.sendmail(from_addr, recipients, msg.as_string())
            return { 'status': 'success', 'channel': 'email', 'recipients': recipients }
        except Exception as e:
            return { 'status': 'error', 'detail': str(e) }

    def _post_webhook(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read().decode('utf-8', errors='ignore')
                return { 'status': 'success', 'http_status': resp.status, 'response': body }
        except Exception as e:
            return { 'status': 'error', 'detail': str(e) }

    def send_slack(self, text: str) -> Dict[str, Any]:
        slack_cfg = self._cfg.get('slack') or {}
        url = slack_cfg.get('webhook_url')
        if not url:
            return { 'status': 'error', 'detail': 'Slack webhook_url이 설정되어 있지 않습니다.' }
        payload = { 'text': text }
        return self._post_webhook(url, payload)

    def send_discord(self, content: str) -> Dict[str, Any]:
        disc_cfg = self._cfg.get('discord') or {}
        url = disc_cfg.get('webhook_url')
        if not url:
            return { 'status': 'error', 'detail': 'Discord webhook_url이 설정되어 있지 않습니다.' }
        payload = { 'content': content }
        return self._post_webhook(url, payload)

    # ---------------------- 멀티 채널 브로드캐스트 ----------------------
    def broadcast(self, title: str, message: str) -> Dict[str, Any]:
        """활성화된 채널로 일괄 전송"""
        ch = self.channels_enabled()
        results: Dict[str, Any] = {}
        if ch.get('email'):
            results['email'] = self.send_email(subject=title, message=message)
        if ch.get('slack'):
            results['slack'] = self.send_slack(text=f"{title}\n{message}")
        if ch.get('discord'):
            results['discord'] = self.send_discord(content=f"**{title}**\n{message}")
        if not results:
            results['note'] = '활성화된 채널이 없습니다.'
        return results
