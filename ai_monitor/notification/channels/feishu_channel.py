# -*- coding: utf-8 -*-
import httpx

from ai_monitor.config.settings import get_settings
from ai_monitor.notification.base import AbstractNotificationChannel
from ai_monitor.store.database import get_session
from ai_monitor.store.models import NotificationConfig
from sqlalchemy import select


class FeishuChannel(AbstractNotificationChannel):
    name = "feishu"

    async def send(self, title: str, body: str, severity: str = "warning") -> bool:
        webhook_url = await _get_feishu_webhook_url()
        if not webhook_url:
            return False
        payload = {
            "msg_type": "text",
            "content": {
                "text": f"[{severity.upper()}] {title}\n\n{body}",
            },
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(webhook_url, json=payload)
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            return resp.is_success and data.get("code", 0) == 0


async def _get_feishu_webhook_url() -> str:
    async with get_session() as session:
        result = await session.execute(
            select(NotificationConfig).where(NotificationConfig.channel_name == "feishu")
        )
        row = result.scalar_one_or_none()
        if row and row.is_enabled and row.config:
            url = (row.config or {}).get("webhook_url") or ""
            if url:
                return url

    settings = get_settings()
    return settings.FEISHU_WEBHOOK_URL or ""
