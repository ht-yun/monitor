# -*- coding: utf-8 -*-
"""Route alerts to configured notification channels."""

import logging
from typing import Dict, List, Optional

from ai_monitor.notification.base import AbstractNotificationChannel
from ai_monitor.notification.channels.console_channel import ConsoleChannel
from ai_monitor.notification.channels.dingtalk_channel import DingTalkChannel
from ai_monitor.notification.channels.email_channel import EmailChannel
from ai_monitor.notification.channels.feishu_channel import FeishuChannel
from ai_monitor.notification.channels.slack_channel import SlackChannel
from ai_monitor.notification.channels.discord_channel import DiscordChannel
from ai_monitor.notification.channels.wechat_work_channel import WeChatWorkChannel
from ai_monitor.notification.channels.webhook_channel import WebhookChannel
from ai_monitor.notification.channels.sms_channel import SMSChannel

logger = logging.getLogger("ai_monitor")

CHANNEL_MAP: Dict[str, AbstractNotificationChannel] = {
    "console": ConsoleChannel(),
    "webhook": WebhookChannel(),
    "dingtalk": DingTalkChannel(),
    "feishu": FeishuChannel(),
    "email": EmailChannel(),
    "slack": SlackChannel(),
    "discord": DiscordChannel(),
    "wechat_work": WeChatWorkChannel(),
    "sms": SMSChannel(),
}


class NotificationDispatcher:
    def __init__(self):
        self.last_channels_used: List[str] = []

    async def send_alert(
        self,
        rule_name: str,
        severity: str,
        platform: str,
        job_id: str,
        summary: str,
        matched_count: int,
        channels: Optional[List[str]] = None,
        sample: str = "",
    ) -> None:
        channels = channels or ["console"]
        title = f"[{platform}] {rule_name}"
        body = (
            f"{summary}\n\n"
            f"任务: {job_id}\n"
            f"匹配条数: {matched_count}\n"
        )
        if sample:
            body += f"样例: {sample[:300]}"

        self.last_channels_used = []
        for name in channels:
            channel = CHANNEL_MAP.get(name)
            if not channel:
                logger.warning("Unknown notification channel: %s", name)
                continue
            try:
                ok = await channel.send(title, body, severity)
                if ok:
                    self.last_channels_used.append(name)
            except Exception as e:
                logger.warning("Channel %s failed: %s", name, e)

        if not self.last_channels_used:
            await ConsoleChannel().send(title, body, severity)
            self.last_channels_used = ["console"]
