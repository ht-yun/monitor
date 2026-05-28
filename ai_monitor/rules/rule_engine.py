# -*- coding: utf-8 -*-
"""Rule engine - loads rules, evaluates all, manages state."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import select

from ai_monitor.rules.base import (
    RuleConfigModel,
    RuleEvaluationResult,
    AbstractMonitorRule,
)
from ai_monitor.rules.rule_registry import RuleRegistry
from ai_monitor.store.database import get_session
from ai_monitor.store.models import MonitoringJob, RuleConfig as RuleConfigRow

logger = logging.getLogger("ai_monitor")


class RuleEngine:
    """Evaluates monitoring rules against crawled content and AI analysis."""

    def __init__(self):
        self._active_rules: Dict[str, AbstractMonitorRule] = {}
        self._last_triggered: Dict[str, datetime] = {}
        self._historical_stats: Dict[str, List[Dict]] = {}

    async def load_rules_from_db(self, rule_set_ids: Optional[List[str]] = None):
        """Load active rules, optionally filtered by rule set ids."""
        self._active_rules.clear()
        async with get_session() as session:
            result = await session.execute(
                select(RuleConfigRow).where(RuleConfigRow.is_active == True)
            )
            for record in result.scalars():
                if rule_set_ids and not _rule_matches_sets(record, rule_set_ids):
                    continue
                await self._add_rule_from_row(record)

    async def load_rules_for_job(self, job_id: str):
        """Load rules and historical stats for a specific monitoring job."""
        rule_set_ids = await self._get_job_rule_sets(job_id)
        await self._load_historical_from_db(job_id)
        await self.load_rules_from_db(rule_set_ids if rule_set_ids else None)

    async def _get_job_rule_sets(self, job_id: str) -> List[str]:
        async with get_session() as session:
            result = await session.execute(
                select(MonitoringJob).where(MonitoringJob.job_id == job_id)
            )
            job = result.scalar_one_or_none()
            if job and job.rule_set_ids:
                return list(job.rule_set_ids)
        return []

    async def _load_historical_from_db(self, job_id: str):
        async with get_session() as session:
            result = await session.execute(
                select(MonitoringJob).where(MonitoringJob.job_id == job_id)
            )
            job = result.scalar_one_or_none()
            if job and job.historical_stats:
                self._historical_stats[job_id] = list(job.historical_stats)[-720:]

    async def _add_rule_from_row(self, record: RuleConfigRow):
        config = RuleConfigModel(
            rule_id=record.rule_id,
            name=record.name,
            rule_type=record.rule_type,
            description=record.description or "",
            params=record.params or {},
            severity=record.severity or "warning",
            notification_channels=record.notification_channels or [],
            cooldown_minutes=record.cooldown_minutes or 30,
        )
        rule_class = RuleRegistry.get(config.rule_type)
        self._active_rules[config.rule_id] = rule_class(config)

    async def add_rule(self, config: RuleConfigModel):
        rule_class = RuleRegistry.get(config.rule_type)
        self._active_rules[config.rule_id] = rule_class(config)

    def remove_rule(self, rule_id: str):
        self._active_rules.pop(rule_id, None)

    async def evaluate_all(
        self,
        content_items: List[Dict],
        analysis_results: List[Dict],
        job_id: str,
        platform: str,
    ) -> List[RuleEvaluationResult]:
        triggered_results = []

        for rule_id, rule in self._active_rules.items():
            if rule.config.platform and rule.config.platform != platform:
                continue

            last = self._last_triggered.get(rule_id)
            if last and (datetime.utcnow() - last).total_seconds() < rule.config.cooldown_minutes * 60:
                continue

            historical = self._historical_stats.get(job_id, [])

            try:
                result = await rule.evaluate(content_items, analysis_results, historical)
                if result.triggered:
                    self._last_triggered[rule_id] = datetime.utcnow()
                    triggered_results.append(result)
            except Exception as e:
                logger.warning("Rule %s evaluation failed: %s", rule_id, e)

        await self._update_historical(job_id, analysis_results)
        return triggered_results

    async def _update_historical(self, job_id: str, analysis_results: List[Dict]):
        if job_id not in self._historical_stats:
            self._historical_stats[job_id] = []

        total = len(analysis_results)
        negative_count = sum(1 for r in analysis_results if r.get("sentiment") == "negative")
        positive_count = sum(1 for r in analysis_results if r.get("sentiment") == "positive")

        stats = {
            "count": total,
            "negative_ratio": negative_count / max(total, 1),
            "positive_ratio": positive_count / max(total, 1),
            "avg_sentiment": sum(r.get("sentiment_score", 0.5) for r in analysis_results) / max(total, 1),
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._historical_stats[job_id].append(stats)
        if len(self._historical_stats[job_id]) > 720:
            self._historical_stats[job_id] = self._historical_stats[job_id][-720:]

        async with get_session() as session:
            result = await session.execute(
                select(MonitoringJob).where(MonitoringJob.job_id == job_id)
            )
            job = result.scalar_one_or_none()
            if job:
                job.historical_stats = self._historical_stats[job_id]

    def get_historical_stats(self, job_id: str, lookback_hours: int = 24) -> List[Dict]:
        history = self._historical_stats.get(job_id, [])
        if not history or lookback_hours <= 0:
            return history
        cutoff = datetime.utcnow() - timedelta(hours=lookback_hours)
        return [
            h for h in history
            if datetime.fromisoformat(h["timestamp"]) >= cutoff
        ]


def _rule_matches_sets(record: RuleConfigRow, rule_set_ids: List[str]) -> bool:
    if record.rule_id in rule_set_ids:
        return True
    if getattr(record, "rule_set", None) and record.rule_set in rule_set_ids:
        return True
    return False
