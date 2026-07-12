# -*- coding: utf-8 -*-
"""API router for system configuration management."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from sqlalchemy import select

from ai_monitor.config.settings import get_settings
from ai_monitor.store.database import get_session
from ai_monitor.store.models import NotificationConfig, SystemConfig

router = APIRouter(prefix="/api/system", tags=["system"])


class ConfigValue(BaseModel):
    config_group: str
    config_key: str
    config_value: str = ""
    display_name: str = ""
    is_secret: bool = False


class ConfigUpdateRequest(BaseModel):
    values: list[ConfigValue]


# ===== Get all configs =====

def _mask(value: str) -> str:
    if not value or len(value) < 8:
        return ""
    return value[:4] + "****" + value[-4:]


CONFIG_GROUPS = {
    "notifications": {
        "dingtalk_webhook": {"display": "\u9489\u9489 Webhook", "secret": True},
        "wechat_work_webhook": {"display": "\u4f01\u4e1a\u5fae\u4fe1 Webhook", "secret": True},
        "slack_webhook": {"display": "Slack Webhook", "secret": True},
        "discord_webhook": {"display": "Discord Webhook", "secret": True},
        "email_smtp_host": {"display": "Email SMTP \u4e3b\u673a", "secret": False},
        "email_smtp_port": {"display": "Email SMTP \u7aef\u53e3", "secret": False},
        "email_from": {"display": "Email \u53d1\u4ef6\u4eba", "secret": False},
        "email_username": {"display": "Email \u7528\u6237\u540d", "secret": False},
        "email_password": {"display": "Email \u5bc6\u7801", "secret": True},
    },
    "tokens": {
        "github_token": {"display": "GitHub Token", "secret": True},
        "gitee_token": {"display": "Gitee Token", "secret": True},
    },
    "ai": {
        "openai_api_key": {"display": "OpenAI API Key", "secret": True},
        "openai_api_base": {"display": "OpenAI API Base URL", "secret": False},
        "openai_model": {"display": "AI \u6a21\u578b", "secret": False},
    },
    "platform_cookies": {
        "xhs_cookie": {"display": "\u5c0f\u7ea2\u4e66 Cookie", "secret": True},
        "dy_cookie": {"display": "\u6296\u97f3 Cookie", "secret": True},
        "ks_cookie": {"display": "\u5feb\u624b Cookie", "secret": True},
        "wb_cookie": {"display": "\u5fae\u535a Cookie", "secret": True},
        "bili_cookie": {"display": "B\u7ad9 Cookie", "secret": True},
        "zhihu_cookie": {"display": "\u77e5\u4e4e Cookie", "secret": True},
        "tieba_cookie": {"display": "\u8d34\u5427 Cookie", "secret": True},
    },
}


@router.get("/config")
async def get_system_config():
    settings = get_settings()
    result = {}

    for group, keys in CONFIG_GROUPS.items():
        group_items = []
        for key, meta in keys.items():
            db_val = await _get_db_config(group, key)
            if db_val is not None:
                value = db_val
            else:
                env_key = f"AIMONITOR_{key.upper()}"
                value = getattr(settings, key.upper(), None) or ""
            group_items.append({
                "config_key": key,
                "config_value": _mask(value) if meta["secret"] else value,
                "display_name": meta["display"],
                "is_secret": meta["secret"],
                "configured": bool(value),
            })
        result[group] = {
            "display_name": _group_label(group),
            "items": group_items,
        }
    return result


MC_CONFIG_PATH = r"D:\aaa\ing\monitor\MediaCrawler\config\base_config.py"

PLATFORM_MAP = {
    "xhs_cookie": ("xhs", "xhs"),
    "dy_cookie": ("dy", "dy"),
    "ks_cookie": ("ks", "ks"),
    "bili_cookie": ("bili", "bili"),
    "wb_cookie": ("wb", "wb"),
    "zhihu_cookie": ("zhihu", "zhihu"),
    "tieba_cookie": ("tieba", "tieba"),
}


def _escape_cookie_for_python(value: str) -> str:
    """Escape a cookie value for safe insertion into a Python string literal."""
    return value.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")


async def _write_cookie_to_mc_config(config_key: str, config_value: str) -> bool:
    """Write a platform cookie to MediaCrawler config/base_config.py"""
    import re, os
    
    platform = PLATFORM_MAP.get(config_key)
    if not platform:
        return False
    platform_key, _ = platform
    
    filepath = MC_CONFIG_PATH
    if not os.path.exists(filepath):
        return False
    
    try:
        content = open(filepath, "r", encoding="utf-8").read()
        escaped_value = config_value.replace("\\", "\\\\").replace('"', '\\"')
        new_line = f"COOKIES = \"{escaped_value}\""
        content = re.sub(r'COOKIES\s*=\s*"[^"]*"', new_line, content)
        open(filepath, "w", encoding="utf-8").write(content)
        return True
    except Exception:
        return False


@router.put("/config")
async def update_system_config(body: ConfigUpdateRequest):
    exported = []
    for val in body.values:
        await _set_db_config(val.config_group, val.config_key, val.config_value)
        # Auto-export platform cookies to MediaCrawler config
        if val.config_group == "platform_cookies" and val.config_key in PLATFORM_MAP:
            ok = await _write_cookie_to_mc_config(val.config_key, val.config_value)
            if ok:
                exported.append(val.config_key)
    result = {"saved": True}
    if exported:
        result["exported_to_crawler"] = [p.replace("_cookie", "") for p in exported]
    return result


@router.post("/config/export-cookies")
async def export_cookies_to_crawler():
    """Export all platform cookies from database to MediaCrawler config."""
    from sqlalchemy import select
    from ai_monitor.store.database import get_session
    from ai_monitor.store.models import SystemConfig
    
    imported = []
    async with get_session() as session:
        result = await session.execute(
            select(SystemConfig).where(SystemConfig.config_group == "platform_cookies")
        )
        rows = list(result.scalars().all())
    
    for row in rows:
        if row.config_key in PLATFORM_MAP and row.config_value:
            ok = await _write_cookie_to_mc_config(row.config_key, row.config_value)
            if ok:
                imported.append(row.config_key.replace("_cookie", ""))
    
    return {"exported": imported, "count": len(imported)}



async def _get_db_config(group: str, key: str) -> Optional[str]:
    async with get_session() as session:
        result = await session.execute(
            select(SystemConfig).where(
                SystemConfig.config_group == group,
                SystemConfig.config_key == key,
            )
        )
        row = result.scalar_one_or_none()
        return row.config_value if row else None


async def _set_db_config(group: str, key: str, value: str) -> None:
    async with get_session() as session:
        result = await session.execute(
            select(SystemConfig).where(
                SystemConfig.config_group == group,
                SystemConfig.config_key == key,
            )
        )
        row = result.scalar_one_or_none()
        if row:
            row.config_value = value
            row.updated_at = datetime.utcnow()
        else:
            meta = CONFIG_GROUPS.get(group, {}).get(key, {})
            session.add(SystemConfig(
                config_group=group,
                config_key=key,
                config_value=value,
                display_name=meta.get("display", key),
                is_secret=meta.get("secret", False),
            ))


def _group_label(group: str) -> str:
    labels = {
        "notifications": "\u901a\u77e5\u6e20\u9053\u914d\u7f6e",
        "tokens": "Token \u914d\u7f6e",
        "ai": "AI \u914d\u7f6e",
        "platform_cookies": "\u793e\u5a92\u5e73\u53f0 Cookie \u914d\u7f6e",
    }
    return labels.get(group, group)
