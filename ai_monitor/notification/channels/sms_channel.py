# -*- coding: utf-8 -*-
"""Alibaba Cloud SMS notification channel."""

import hashlib
import hmac
import logging
import uuid
from datetime import datetime, timezone
from urllib.parse import quote

import httpx

from ai_monitor.config.settings import get_settings
from ai_monitor.notification.base import AbstractNotificationChannel

logger = logging.getLogger("ai_monitor")


class SMSChannel(AbstractNotificationChannel):
    name = "sms"

    async def send(self, title: str, body: str, severity: str = "warning") -> bool:
        settings = get_settings()
        if not all([
            settings.SMS_ACCESS_KEY_ID,
            settings.SMS_ACCESS_KEY_SECRET,
            settings.SMS_SIGN_NAME,
            settings.SMS_TEMPLATE_CODE,
        ]):
            logger.debug("SMS channel not configured")
            return False

        phones = (settings.SMS_PHONE_NUMBERS or "").strip()
        if not phones:
            logger.warning("SMS: set AIMONITOR_SMS_PHONE_NUMBERS=13800138000")
            return False

        text = f"[{severity}] {title}: {body[:120]}"
        ok = True
        for num in phones.split(","):
            num = num.strip()
            if not num:
                continue
            if not await self._send_one(settings, num, text):
                ok = False
        return ok

    async def _send_one(self, settings, phone: str, text: str) -> bool:
        params = {
            "AccessKeyId": settings.SMS_ACCESS_KEY_ID,
            "Action": "SendSms",
            "Format": "JSON",
            "PhoneNumbers": phone,
            "RegionId": "cn-hangzhou",
            "SignName": settings.SMS_SIGN_NAME,
            "SignatureMethod": "HMAC-SHA1",
            "SignatureNonce": str(uuid.uuid4()),
            "SignatureVersion": "1.0",
            "TemplateCode": settings.SMS_TEMPLATE_CODE,
            "TemplateParam": f'{{"content":"{text[:100].replace(chr(34), "")}"}}',
            "Timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "Version": "2017-05-25",
        }
        sorted_params = sorted(params.items())
        query = "&".join(
            f"{quote(k, safe='')}={quote(str(v), safe='')}" for k, v in sorted_params
        )
        string_to_sign = f"GET&%2F&{quote(query, safe='')}"
        key = (settings.SMS_ACCESS_KEY_SECRET + "&").encode()
        signature = hmac.new(key, string_to_sign.encode(), hashlib.sha1).digest()
        import base64
        sig_b64 = base64.b64encode(signature).decode()
        url = f"https://dysmsapi.aliyuncs.com/?{query}&Signature={quote(sig_b64)}"

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(url)
                data = resp.json()
                if data.get("Code") == "OK":
                    return True
                logger.warning("SMS API error: %s", data)
        except Exception as e:
            logger.warning("SMS send failed: %s", e)
        return False
