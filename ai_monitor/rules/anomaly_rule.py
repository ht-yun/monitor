# -*- coding: utf-8 -*-
"""Anomaly/volume spike detection rule."""

from typing import Dict, List

from ai_monitor.rules.base import (
    AbstractMonitorRule,
    RuleConfigModel,
    RuleEvaluationResult,
)
from ai_monitor.rules.rule_registry import RuleRegistry


class AnomalyMonitorRule(AbstractMonitorRule):
    """Trigger when content volume or sentiment deviates significantly from baseline."""

    async def evaluate(
        self,
        content_items: List[Dict],
        analysis_results: List[Dict],
        historical_data: List[Dict] = None,
    ) -> RuleEvaluationResult:
        spike_threshold = self.config.params.get("spike_threshold", 2.0)

        if not historical_data:
            return RuleEvaluationResult(
                rule_id=self.config.rule_id,
                rule_name=self.config.name,
                rule_type=self.config.rule_type,
                triggered=False,
                severity=self.config.severity,
                summary="无历史数据用于对比",
            )

        current_count = len(content_items)
        hist_counts = [h.get("count", 0) for h in historical_data]
        if not hist_counts:
            return RuleEvaluationResult(
                rule_id=self.config.rule_id,
                rule_name=self.config.name,
                rule_type=self.config.rule_type,
                triggered=False,
                severity=self.config.severity,
            )

        avg_count = sum(hist_counts) / len(hist_counts)
        if avg_count < 1:
            return RuleEvaluationResult(
                rule_id=self.config.rule_id,
                rule_name=self.config.name,
                rule_type=self.config.rule_type,
                triggered=False,
                severity=self.config.severity,
            )

        ratio = current_count / max(avg_count, 1)
        triggered = ratio >= spike_threshold or ratio <= (1 / max(spike_threshold, 1))

        return RuleEvaluationResult(
            rule_id=self.config.rule_id,
            rule_name=self.config.name,
            rule_type=self.config.rule_type,
            triggered=triggered,
            severity=self.config.severity,
            matched_items=content_items if triggered else [],
            summary=(
                f"内容量异常: 当前 {current_count} 条，"
                f"历史均值 {avg_count:.0f} 条，比值 {ratio:.1f}x"
                if triggered
                else ""
            ),
            metric_value=ratio,
            threshold=spike_threshold,
        )


RuleRegistry.register("anomaly", AnomalyMonitorRule)
