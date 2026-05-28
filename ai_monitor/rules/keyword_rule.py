# -*- coding: utf-8 -*-
"""Keyword-based monitoring rule."""

from typing import Dict, List

from ai_monitor.rules.base import (
    AbstractMonitorRule,
    RuleConfigModel,
    RuleEvaluationResult,
)
from ai_monitor.rules.rule_registry import RuleRegistry


class KeywordMonitorRule(AbstractMonitorRule):
    """Trigger when specified keywords appear in content."""

    async def evaluate(
        self,
        content_items: List[Dict],
        analysis_results: List[Dict],
        historical_data: List[Dict] = None,
    ) -> RuleEvaluationResult:
        keywords = self.config.params.get("keywords", [])
        min_mentions = self.config.params.get("min_mentions", 1)

        if not keywords:
            return RuleEvaluationResult(
                rule_id=self.config.rule_id,
                rule_name=self.config.name,
                rule_type=self.config.rule_type,
                triggered=False,
                severity=self.config.severity,
            )

        matched = []
        keywords_lower = [kw.lower() for kw in keywords]

        for item in content_items:
            title = (item.get("title") or "").lower()
            desc = (item.get("desc") or "").lower()
            content = (item.get("content") or "").lower()
            combined = f"{title} {desc} {content}"

            matched_keywords = [kw for kw in keywords_lower if kw in combined]
            if matched_keywords:
                matched.append({
                    "content_id": item.get("note_id") or item.get("video_id"),
                    "title": item.get("title", ""),
                    "matched_keywords": matched_keywords,
                })

        triggered = len(matched) >= min_mentions
        return RuleEvaluationResult(
            rule_id=self.config.rule_id,
            rule_name=self.config.name,
            rule_type=self.config.rule_type,
            triggered=triggered,
            severity=self.config.severity,
            matched_items=matched,
            summary=(
                f"匹配到 {len(matched)} 条包含关键词的内容: {', '.join(keywords[:5])}"
                if triggered
                else ""
            ),
            metric_value=float(len(matched)),
            threshold=float(min_mentions),
        )


RuleRegistry.register("keyword", KeywordMonitorRule)
