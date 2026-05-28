# -*- coding: utf-8 -*-
from pathlib import Path

from fastapi import APIRouter

from ai_monitor.config.settings import get_settings

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/status")
async def system_status():
    settings = get_settings()
    mc = Path(settings.MEDIACRAWLER_PATH)
    return {
        "mediacrawler": {"ok": mc.exists(), "path": str(mc)},
        "openai_configured": bool(settings.OPENAI_API_KEY),
        "github_token_configured": bool(settings.GITHUB_TOKEN),
        "gitee_token_configured": bool(settings.GITEE_TOKEN),
        "notifications": {
            "dingtalk": bool(settings.DINGTALK_WEBHOOK_URL),
            "feishu": bool(settings.FEISHU_WEBHOOK_URL),
            "slack": bool(settings.SLACK_WEBHOOK_URL),
            "discord": bool(settings.DISCORD_WEBHOOK_URL),
            "wechat_work": bool(settings.WECHAT_WORK_WEBHOOK_URL),
            "email": bool(settings.EMAIL_SMTP_HOST),
            "webhook": bool(settings.WEBHOOK_URL),
            "sms": bool(settings.SMS_ACCESS_KEY_ID and settings.SMS_TEMPLATE_CODE),
        },
    }


@router.post("/sync-notifications")
async def sync_notifications():
    from ai_monitor.config.notification_loader import sync_notifications_from_yaml

    n = await sync_notifications_from_yaml()
    return {"synced": n}
