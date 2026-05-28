# -*- coding: utf-8 -*-
import httpx

from ai_monitor.config.settings import get_settings
from ai_monitor.notification.base import AbstractNotificationChannel


class WeChatWorkChannel(AbstractNotificationChannel):
    name = "wechat_work"

    async def send(self, title: str, body: str, severity: str = "warning") -> bool:
        settings = get_settings()
        if not settings.WECHAT_WORK_WEBHOOK_URL:
            return False
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"**[{severity.upper()}] {title}**\n{body[:1500]}",
            },
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(settings.WECHAT_WORK_WEBHOOK_URL, json=payload)
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            return resp.is_success and data.get("errcode", 0) == 0
