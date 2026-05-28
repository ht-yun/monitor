# -*- coding: utf-8 -*-
"""Import joyoung (九阳) brand rules into database."""

import asyncio
import yaml
from pathlib import Path

from sqlalchemy import select

from ai_monitor.store.database import init_db, get_session
from ai_monitor.store.models import RuleConfig


async def main():
    await init_db()
    rules_path = Path(__file__).resolve().parent.parent / "config" / "rules.yaml"
    with open(rules_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    rule_set = data.get("rule_sets", {}).get("joyoung_brand", {})
    imported = 0
    async with get_session() as session:
        for rule in rule_set.get("rules", []):
            existing = await session.execute(
                select(RuleConfig).where(RuleConfig.rule_id == rule["rule_id"])
            )
            if existing.scalar_one_or_none():
                continue
            session.add(
                RuleConfig(
                    rule_id=rule["rule_id"],
                    name=rule["name"],
                    rule_type=rule["rule_type"],
                    description=rule.get("description", ""),
                    params=rule.get("params", {}),
                    severity=rule.get("severity", "warning"),
                    notification_channels=rule.get("notification_channels", ["console"]),
                    cooldown_minutes=rule.get("cooldown_minutes", 30),
                    is_active=True,
                )
            )
            imported += 1
    print(f"[九阳] Imported {imported} brand rules")


if __name__ == "__main__":
    asyncio.run(main())
