# -*- coding: utf-8 -*-
from typing import List

from fastapi import APIRouter
from sqlalchemy import select

from ai_monitor.store.database import get_session
from ai_monitor.store.models import RuleConfig

router = APIRouter(prefix="/api/rules", tags=["rules"])


@router.get("/sets")
async def list_rule_sets():
    import yaml
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent.parent / "config" / "rules.yaml"
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return {
        "rule_sets": [
            {"id": k, "name": v.get("name", k), "description": v.get("description", "")}
            for k, v in (data.get("rule_sets") or {}).items()
        ]
    }


@router.get("")
async def list_rules():
    async with get_session() as session:
        result = await session.execute(
            select(RuleConfig).where(RuleConfig.is_active == True)
        )
        rows = result.scalars().all()
    return {
        "rules": [
            {
                "rule_id": r.rule_id,
                "name": r.name,
                "rule_type": r.rule_type,
                "severity": r.severity,
                "description": r.description,
                "notification_channels": r.notification_channels,
                "rule_set": getattr(r, "rule_set", "") or "",
            }
            for r in rows
        ]
    }


@router.post("/import-default")
async def import_default_rules():
    import yaml
    from pathlib import Path

    rules_path = Path(__file__).resolve().parent.parent.parent / "config" / "rules.yaml"
    with open(rules_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    imported = 0
    async with get_session() as session:
        for set_name, rule_set in data.get("rule_sets", {}).items():
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
                        notification_channels=rule.get("notification_channels", []),
                        cooldown_minutes=rule.get("cooldown_minutes", 30),
                        rule_set=set_name,
                        is_active=True,
                    )
                )
                imported += 1
    return {"imported": imported}


@router.post("/import-joyoung")
async def import_joyoung_rules():
    import yaml
    from pathlib import Path

    rules_path = Path(__file__).resolve().parent.parent.parent / "config" / "rules.yaml"
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
                    notification_channels=rule.get(
                        "notification_channels", ["console"]
                    ),
                    cooldown_minutes=rule.get("cooldown_minutes", 30),
                    rule_set="joyoung_brand",
                    is_active=True,
                )
            )
            imported += 1
    return {"imported": imported}
