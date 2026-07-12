# -*- coding: utf-8 -*-
from pathlib import Path

from fastapi import APIRouter
from sqlalchemy import select

from ai_monitor.config.settings import get_settings
from ai_monitor.store.database import get_session
from ai_monitor.store.models import NotificationConfig

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/status")
async def system_status():
    settings = get_settings()
    mc = Path(settings.MEDIACRAWLER_PATH)
    db_notifications = await _notification_enabled_map()
    return {
        "mediacrawler": {"ok": mc.exists(), "path": str(mc)},
        "openai_configured": bool(settings.OPENAI_API_KEY),
        "github_token_configured": bool(settings.GITHUB_TOKEN),
        "gitee_token_configured": bool(settings.GITEE_TOKEN),
        "feishu_app_configured": bool(settings.FEISHU_APP_ID and settings.FEISHU_APP_SECRET),
        "feishu_repo_doc_configured": bool(settings.FEISHU_REPO_DOC_TOKEN),
        "notifications": {
            "dingtalk": db_notifications.get("dingtalk") or bool(settings.DINGTALK_WEBHOOK_URL),
            "feishu": db_notifications.get("feishu") or bool(settings.FEISHU_WEBHOOK_URL),
            "slack": db_notifications.get("slack") or bool(settings.SLACK_WEBHOOK_URL),
            "discord": db_notifications.get("discord") or bool(settings.DISCORD_WEBHOOK_URL),
            "wechat_work": db_notifications.get("wechat_work") or bool(settings.WECHAT_WORK_WEBHOOK_URL),
            "email": db_notifications.get("email") or bool(settings.EMAIL_SMTP_HOST),
            "webhook": db_notifications.get("webhook") or bool(settings.WEBHOOK_URL),
            "sms": db_notifications.get("sms") or bool(settings.SMS_ACCESS_KEY_ID and settings.SMS_TEMPLATE_CODE),
        },
    }


@router.post("/sync-notifications")
async def sync_notifications():
    from ai_monitor.config.notification_loader import sync_notifications_from_yaml

    n = await sync_notifications_from_yaml()
    return {"synced": n}


async def _notification_enabled_map() -> dict:
    async with get_session() as session:
        result = await session.execute(select(NotificationConfig))
        return {row.channel_name: bool(row.is_enabled) for row in result.scalars().all()}
