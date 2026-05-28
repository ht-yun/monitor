# -*- coding: utf-8 -*-
"""Rule registry - discoverable rule pattern."""

from typing import Dict, Type

from ai_monitor.rules.base import AbstractMonitorRule


class RuleRegistry:
    """Global registry of monitoring rule classes.

    Usage:
        RuleRegistry.register("keyword", KeywordMonitorRule)
        rule_class = RuleRegistry.get("keyword")
        rule = rule_class(config)
    """

    _rules: Dict[str, Type[AbstractMonitorRule]] = {}

    @classmethod
    def register(cls, name: str, rule_class: Type[AbstractMonitorRule]):
        cls._rules[name] = rule_class

    @classmethod
    def get(cls, name: str) -> Type[AbstractMonitorRule]:
        if name not in cls._rules:
            # Auto-import built-ins on first use
            if not cls._rules:
                import ai_monitor.rules.keyword_rule  # noqa
                import ai_monitor.rules.sentiment_rule  # noqa
                import ai_monitor.rules.anomaly_rule  # noqa
                import ai_monitor.rules.trend_rule  # noqa
                import ai_monitor.rules.risk_rule  # noqa
            if name not in cls._rules:
                raise ValueError(
                    f"Unknown rule type: {name}. "
                    f"Available: {list(cls._rules.keys())}"
                )
        return cls._rules[name]

    @classmethod
    def list_all(cls) -> list:
        if not cls._rules:
            import ai_monitor.rules.keyword_rule  # noqa
            import ai_monitor.rules.sentiment_rule  # noqa
            import ai_monitor.rules.anomaly_rule  # noqa
            import ai_monitor.rules.trend_rule  # noqa
            import ai_monitor.rules.risk_rule  # noqa
        return list(cls._rules.keys())
