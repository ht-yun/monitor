# -*- coding: utf-8 -*-
import asyncio
import smtplib
from email.mime.text import MIMEText

from ai_monitor.config.settings import get_settings
from ai_monitor.notification.base import AbstractNotificationChannel


class EmailChannel(AbstractNotificationChannel):
    name = "email"

    async def send(self, title: str, body: str, severity: str = "warning") -> bool:
        settings = get_settings()
        if not settings.EMAIL_SMTP_HOST or not settings.EMAIL_FROM:
            return False

        msg = MIMEText(f"[{severity.upper()}] {title}\n\n{body}", "plain", "utf-8")
        msg["Subject"] = f"[AI Monitor][{severity}] {title}"
        msg["From"] = settings.EMAIL_FROM
        msg["To"] = settings.EMAIL_FROM

        def _send():
            with smtplib.SMTP(settings.EMAIL_SMTP_HOST, settings.EMAIL_SMTP_PORT) as server:
                server.starttls()
                if settings.EMAIL_USERNAME and settings.EMAIL_PASSWORD:
                    server.login(settings.EMAIL_USERNAME, settings.EMAIL_PASSWORD)
                server.send_message(msg)
            return True

        return await asyncio.to_thread(_send)
