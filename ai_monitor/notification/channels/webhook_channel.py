# -*- coding: utf-8 -*-
import httpx

from ai_monitor.config.settings import get_settings
from ai_monitor.notification.base import AbstractNotificationChannel


class WebhookChannel(AbstractNotificationChannel):
    name = "webhook"

    async def send(self, title: str, body: str, severity: str = "warning") -> bool:
        settings = get_settings()
        if not settings.WEBHOOK_URL:
            return False
        payload = {
            "title": title,
            "body": body,
            "severity": severity,
            "source": "ai-monitor",
        }
        headers = {}
        if settings.WEBHOOK_SECRET:
            headers["X-Webhook-Secret"] = settings.WEBHOOK_SECRET
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(settings.WEBHOOK_URL, json=payload, headers=headers)
            return resp.is_success
