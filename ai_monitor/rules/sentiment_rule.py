# -*- coding: utf-8 -*-
"""Sentiment threshold monitoring rule."""

from typing import Dict, List

from ai_monitor.rules.base import (
    AbstractMonitorRule,
    RuleConfigModel,
    RuleEvaluationResult,
)
from ai_monitor.rules.rule_registry import RuleRegistry


class SentimentMonitorRule(AbstractMonitorRule):
    """Trigger when sentiment distribution crosses a threshold."""

    async def evaluate(
        self,
        content_items: List[Dict],
        analysis_results: List[Dict],
        historical_data: List[Dict] = None,
    ) -> RuleEvaluationResult:
        target_sentiment = self.config.params.get("sentiment", "negative")
        threshold = self.config.params.get("threshold", 0.3)
        min_sample_size = self.config.params.get("min_sample_size", 5)

        if not analysis_results or len(analysis_results) < min_sample_size:
            return RuleEvaluationResult(
                rule_id=self.config.rule_id,
                rule_name=self.config.name,
                rule_type=self.config.rule_type,
                triggered=False,
                severity=self.config.severity,
                summary=f"样本不足 (需要最少 {min_sample_size}, 当前 {len(analysis_results)})",
            )

        target_count = sum(
            1 for r in analysis_results if r.get("sentiment") == target_sentiment
        )
        ratio = target_count / len(analysis_results)

        matched = [
            r for r in analysis_results if r.get("sentiment") == target_sentiment
        ]

        triggered = ratio >= threshold
        return RuleEvaluationResult(
            rule_id=self.config.rule_id,
            rule_name=self.config.name,
            rule_type=self.config.rule_type,
            triggered=triggered,
            severity=self.config.severity,
            matched_items=matched,
            summary=(
                f"{target_sentiment}内容占比 {ratio:.1%}，超过阈值 {threshold:.0%} "
                f"(共 {target_count}/{len(analysis_results)} 条)"
                if triggered
                else ""
            ),
            metric_value=ratio,
            threshold=threshold,
        )


RuleRegistry.register("sentiment", SentimentMonitorRule)
