# -*- coding: utf-8 -*-
"""Load notifications.yaml into NotificationConfig table."""

import os
import re
from pathlib import Path

import yaml
from sqlalchemy import select

from ai_monitor.store.database import get_session
from ai_monitor.store.models import NotificationConfig


def _resolve_env(value: str) -> str:
    if not isinstance(value, str):
        return value
    match = re.match(r"\$\{(\w+)\}", value.strip())
    if match:
        return os.environ.get(match.group(1), "")
    return value


async def sync_notifications_from_yaml() -> int:
    path = Path(__file__).resolve().parent / "notifications.yaml"
    if not path.exists():
        return 0
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    from ai_monitor.config.settings import get_settings

    settings = get_settings()
    env_map = {
        "email": {
            "smtp_host": settings.EMAIL_SMTP_HOST,
            "smtp_port": settings.EMAIL_SMTP_PORT,
            "from_addr": settings.EMAIL_FROM,
        },
        "dingtalk": {"webhook_url": settings.DINGTALK_WEBHOOK_URL},
        "feishu": {"webhook_url": settings.FEISHU_WEBHOOK_URL},
        "wechat_work": {"webhook_url": settings.WECHAT_WORK_WEBHOOK_URL},
        "slack": {"webhook_url": settings.SLACK_WEBHOOK_URL},
        "discord": {"webhook_url": settings.DISCORD_WEBHOOK_URL},
        "webhook": {"url": settings.WEBHOOK_URL, "secret": settings.WEBHOOK_SECRET},
    }

    synced = 0
    async with get_session() as session:
        for name, cfg in (data.get("channels") or {}).items():
            raw = cfg.get("config") or {}
            resolved = {k: _resolve_env(v) if isinstance(v, str) else v for k, v in raw.items()}
            for k, v in (env_map.get(name) or {}).items():
                if v:
                    resolved[k] = v
            result = await session.execute(
                select(NotificationConfig).where(NotificationConfig.channel_name == name)
            )
            row = result.scalar_one_or_none()
            if row:
                if (
                    name == "feishu"
                    and not resolved.get("webhook_url")
                    and (row.config or {}).get("webhook_url")
                ):
                    resolved = dict(row.config or {})
                    enabled = bool(row.is_enabled)
                else:
                    enabled = bool(cfg.get("enabled", False))
                row.display_name = cfg.get("display_name", name)
                row.is_enabled = enabled
                row.config = resolved
            else:
                session.add(
                    NotificationConfig(
                        channel_name=name,
                        display_name=cfg.get("display_name", name),
                        is_enabled=bool(cfg.get("enabled", False)),
                        config=resolved,
                    )
                )
            synced += 1
    return synced
