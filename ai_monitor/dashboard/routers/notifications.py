# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ai_monitor.config.settings import get_settings
from ai_monitor.notification.channels.feishu_channel import FeishuChannel
from ai_monitor.store.database import get_session
from ai_monitor.store.models import NotificationConfig

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class FeishuBotConfigRequest(BaseModel):
    webhook_url: str
    enabled: bool = True


@router.get("/feishu-bot")
async def get_feishu_bot_config():
    db_cfg = await _get_config()
    settings = get_settings()
    webhook_url = ""
    enabled = False
    source = "none"

    if db_cfg and db_cfg.config:
        webhook_url = db_cfg.config.get("webhook_url") or ""
        enabled = bool(db_cfg.is_enabled)
        source = "database"
    elif settings.FEISHU_WEBHOOK_URL:
        webhook_url = settings.FEISHU_WEBHOOK_URL
        enabled = True
        source = "environment"

    return {
        "enabled": enabled,
        "configured": bool(webhook_url),
        "source": source,
        "masked_webhook_url": _mask_url(webhook_url),
    }


@router.put("/feishu-bot")
async def save_feishu_bot_config(body: FeishuBotConfigRequest):
    url = (body.webhook_url or "").strip()
    if body.enabled and not _looks_like_feishu_webhook(url):
        raise HTTPException(400, "请输入有效的飞书机器人 Webhook 地址")

    async with get_session() as session:
        result = await session.execute(
            select(NotificationConfig).where(NotificationConfig.channel_name == "feishu")
        )
        row = result.scalar_one_or_none()
        payload = {"webhook_url": url}
        if row:
            row.display_name = "飞书机器人"
            row.is_enabled = bool(body.enabled and url)
            row.config = payload
            row.updated_at = datetime.utcnow()
        else:
            session.add(
                NotificationConfig(
                    channel_name="feishu",
                    display_name="飞书机器人",
                    is_enabled=bool(body.enabled and url),
                    config=payload,
                )
            )

    return {"saved": True, "enabled": bool(body.enabled and url), "configured": bool(url)}


@router.post("/feishu-bot/test")
async def test_feishu_bot(payload: dict = None):
    if payload and payload.get("title"):
        ok = await FeishuChannel().send(
            payload["title"],
            payload.get("body", ""),
            payload.get("severity", "info"),
        )
    else:
        ok = await FeishuChannel().send(
            "AI Monitor 飞书机器人测试",
            "这是一条来自 AI Monitor 的测试消息。后续仓库更新和舆情告警会推送到这里。",
            "info",
        )
    if not ok:
        raise HTTPException(400, "飞书机器人未配置或测试发送失败")
    return {"sent": True}


async def _get_config() -> Optional[NotificationConfig]:
    async with get_session() as session:
        result = await session.execute(
            select(NotificationConfig).where(NotificationConfig.channel_name == "feishu")
        )
        return result.scalar_one_or_none()


def _looks_like_feishu_webhook(url: str) -> bool:
    return (
        url.startswith("https://")
        and ("feishu.cn" in url or "larksuite.com" in url)
        and "/open-apis/bot/v2/hook/" in url
    )


def _mask_url(url: str) -> str:
    if not url:
        return ""
    if len(url) <= 24:
        return "***"
    return f"{url[:18]}...{url[-8:]}"
