# -*- coding: utf-8 -*-
import httpx

from ai_monitor.config.settings import get_settings
from ai_monitor.notification.base import AbstractNotificationChannel


class FeishuChannel(AbstractNotificationChannel):
    name = "feishu"

    async def send(self, title: str, body: str, severity: str = "warning") -> bool:
        settings = get_settings()
        if not settings.FEISHU_WEBHOOK_URL:
            return False
        payload = {
            "msg_type": "text",
            "content": {
                "text": f"[{severity.upper()}] {title}\n\n{body}",
            },
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(settings.FEISHU_WEBHOOK_URL, json=payload)
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            return resp.is_success and data.get("code", 0) == 0
