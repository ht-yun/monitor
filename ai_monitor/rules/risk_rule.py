# -*- coding: utf-8 -*-
"""High brand-risk content detection."""

from typing import Dict, List

from ai_monitor.rules.base import (
    AbstractMonitorRule,
    RuleEvaluationResult,
)
from ai_monitor.rules.rule_registry import RuleRegistry


class RiskMonitorRule(AbstractMonitorRule):
    """Trigger when AI risk scores exceed threshold."""

    async def evaluate(
        self,
        content_items: List[Dict],
        analysis_results: List[Dict],
        historical_data: List[Dict] = None,
    ) -> RuleEvaluationResult:
        threshold = float(self.config.params.get("risk_threshold", 0.7))
        min_matches = int(self.config.params.get("min_matches", 1))

        matched = [
            r for r in analysis_results
            if float(r.get("risk_score") or 0) >= threshold
        ]

        triggered = len(matched) >= min_matches
        return RuleEvaluationResult(
            rule_id=self.config.rule_id,
            rule_name=self.config.name,
            rule_type=self.config.rule_type,
            triggered=triggered,
            severity=self.config.severity,
            matched_items=matched,
            summary=(
                f"高风险内容 {len(matched)} 条（风险分 ≥ {threshold}）"
                if triggered
                else ""
            ),
            metric_value=len(matched),
            threshold=threshold,
        )


RuleRegistry.register("risk", RiskMonitorRule)
