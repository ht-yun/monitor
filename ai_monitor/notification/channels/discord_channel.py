# -*- coding: utf-8 -*-
import httpx

from ai_monitor.config.settings import get_settings
from ai_monitor.notification.base import AbstractNotificationChannel


class DiscordChannel(AbstractNotificationChannel):
    name = "discord"

    async def send(self, title: str, body: str, severity: str = "warning") -> bool:
        settings = get_settings()
        if not settings.DISCORD_WEBHOOK_URL:
            return False
        payload = {
            "content": f"**[{severity.upper()}] {title}**\n{body[:1800]}",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(settings.DISCORD_WEBHOOK_URL, json=payload)
            return resp.is_success
