# -*- coding: utf-8 -*-
"""Trend direction change monitoring rule."""

from typing import Dict, List

from ai_monitor.rules.base import (
    AbstractMonitorRule,
    RuleConfigModel,
    RuleEvaluationResult,
)
from ai_monitor.rules.rule_registry import RuleRegistry


class TrendMonitorRule(AbstractMonitorRule):
    """Trigger when a metric shows a significant directional trend change."""

    async def evaluate(
        self,
        content_items: List[Dict],
        analysis_results: List[Dict],
        historical_data: List[Dict] = None,
    ) -> RuleEvaluationResult:
        metric_key = self.config.params.get("metric", "negative_ratio")
        increase_threshold = self.config.params.get("increase_threshold", 0.5)

        lookback_hours = self.config.params.get("lookback_hours", 24)
        filtered = historical_data or []
        if lookback_hours and filtered:
            from datetime import datetime, timedelta

            cutoff = datetime.utcnow() - timedelta(hours=int(lookback_hours))
            def _parse_ts(ts: str) -> datetime:
                ts = (ts or "").replace("Z", "")
                return datetime.fromisoformat(ts)

            filtered = [
                h for h in filtered
                if _parse_ts(h.get("timestamp", "")) >= cutoff
            ]

        if not filtered or len(filtered) < 2:
            return RuleEvaluationResult(
                rule_id=self.config.rule_id,
                rule_name=self.config.name,
                rule_type=self.config.rule_type,
                triggered=False,
                severity=self.config.severity,
                summary="历史数据不足，无法判断趋势",
            )

        hist_values = [h.get(metric_key, 0) for h in filtered]
        current_value = hist_values[-1]
        prev_avg = sum(hist_values[:-1]) / max(len(hist_values) - 1, 1)

        if prev_avg == 0:
            return RuleEvaluationResult(
                rule_id=self.config.rule_id,
                rule_name=self.config.name,
                rule_type=self.config.rule_type,
                triggered=False,
                severity=self.config.severity,
            )

        change_ratio = (current_value - prev_avg) / prev_avg
        triggered = change_ratio >= increase_threshold

        return RuleEvaluationResult(
            rule_id=self.config.rule_id,
            rule_name=self.config.name,
            rule_type=self.config.rule_type,
            triggered=triggered,
            severity=self.config.severity,
            matched_items=analysis_results if triggered else [],
            summary=(
                f"指标 {metric_key} 变化率 {change_ratio:.1%}，"
                f"超过阈值 {increase_threshold:.0%}"
                if triggered
                else ""
            ),
            metric_value=change_ratio,
            threshold=increase_threshold,
        )


RuleRegistry.register("trend", TrendMonitorRule)
