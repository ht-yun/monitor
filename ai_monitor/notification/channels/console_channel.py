# -*- coding: utf-8 -*-
import logging

from ai_monitor.notification.base import AbstractNotificationChannel

logger = logging.getLogger("ai_monitor")


class ConsoleChannel(AbstractNotificationChannel):
    name = "console"

    async def send(self, title: str, body: str, severity: str = "warning") -> bool:
        print(f"\n[ALERT][{severity.upper()}] {title}\n{body}\n")
        logger.info("[alert] %s — %s", title, body[:200])
        return True
