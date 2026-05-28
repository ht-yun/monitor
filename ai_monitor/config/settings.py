# -*- coding: utf-8 -*-
"""Pydantic BaseSettings for AI Monitor configuration.
Supports .env file and environment variables with AIMONITOR_ prefix."""

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # ==================== Database ====================
    DATABASE_URL: str = f"sqlite+aiosqlite:///{PROJECT_ROOT / 'store' / 'ai_monitor.db'}"

    # ==================== AI Provider ====================
    AI_PROVIDER: str = "openai"  # openai | local_llm | bedrock
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_API_BASE: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o-mini"
    AI_MAX_TOKENS: int = 1024
    AI_TEMPERATURE: float = 0.3
    AI_REQUEST_TIMEOUT: int = 60

    # ==================== Scheduler ====================
    SCHEDULER_MAX_JOBS: int = 20
    SCHEDULER_MISFIRE_GRACE_TIME: int = 60

    # ==================== Notification ====================
    # Email
    EMAIL_SMTP_HOST: str = ""
    EMAIL_SMTP_PORT: int = 587
    EMAIL_FROM: str = ""
    EMAIL_USERNAME: str = ""
    EMAIL_PASSWORD: str = ""

    # SMS (Alibaba Cloud)
    SMS_ACCESS_KEY_ID: str = ""
    SMS_ACCESS_KEY_SECRET: str = ""
    SMS_SIGN_NAME: str = ""
    SMS_TEMPLATE_CODE: str = ""
    SMS_PHONE_NUMBERS: str = ""  # comma-separated

    # DingTalk
    DINGTALK_WEBHOOK_URL: str = ""

    # Feishu (Lark)
    FEISHU_WEBHOOK_URL: str = ""

    # WeChat Work
    WECHAT_WORK_WEBHOOK_URL: str = ""

    # Slack
    SLACK_WEBHOOK_URL: str = ""

    # Discord
    DISCORD_WEBHOOK_URL: str = ""

    # Generic Webhook
    WEBHOOK_URL: str = ""
    WEBHOOK_SECRET: str = ""

    # ==================== Dashboard ====================
    DASHBOARD_HOST: str = "0.0.0.0"
    DASHBOARD_PORT: int = 8081
    DASHBOARD_SECRET_KEY: str = "change-me-in-production"

    # ==================== MediaCrawler ====================
    MEDIACRAWLER_PATH: str = str(PROJECT_ROOT.parent / "MediaCrawler")

    # ==================== Repository watch (GitHub / Gitee) ====================
    GITHUB_TOKEN: Optional[str] = None
    GITEE_TOKEN: Optional[str] = None
    REPO_WATCH_INTERVAL_SECONDS: int = 3600  # 1 hour

    # ==================== Monitoring ====================
    MAX_ALERTS_PER_HOUR: int = 20
    DEFAULT_COOLDOWN_MINUTES: int = 30

    model_config = {
        "env_file": str(PROJECT_ROOT / ".env"),
        "env_prefix": "AIMONITOR_",
        "extra": "ignore",
    }


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
