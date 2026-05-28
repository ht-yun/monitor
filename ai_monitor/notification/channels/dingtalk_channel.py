# -*- coding: utf-8 -*-
import httpx

from ai_monitor.config.settings import get_settings
from ai_monitor.notification.base import AbstractNotificationChannel


class DingTalkChannel(AbstractNotificationChannel):
    name = "dingtalk"

    async def send(self, title: str, body: str, severity: str = "warning") -> bool:
        settings = get_settings()
        if not settings.DINGTALK_WEBHOOK_URL:
            return False
        text = f"### {title}\n\n**级别**: {severity}\n\n{body}"
        payload = {
            "msgtype": "markdown",
            "markdown": {"title": title, "text": text},
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(settings.DINGTALK_WEBHOOK_URL, json=payload)
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            return resp.is_success and data.get("errcode", 0) == 0
