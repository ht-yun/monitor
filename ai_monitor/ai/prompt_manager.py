# -*- coding: utf-8 -*-
"""Manage and render AI prompt templates."""

from ai_monitor.config import prompts


class PromptManager:
    """Load and render prompt templates."""

    _templates = {
        "sentiment_analysis": prompts.SENTIMENT_ANALYSIS,
        "topic_extraction": prompts.TOPIC_EXTRACTION,
        "batch_summary": prompts.BATCH_SUMMARY,
        "anomaly_detection": prompts.ANOMALY_DETECTION,
        "risk_assessment": prompts.RISK_ASSESSMENT,
        "alert_summary": prompts.ALERT_SUMMARY,
    }

    @classmethod
    def get(cls, name: str) -> str:
        """Get a prompt template by name."""
        template = cls._templates.get(name)
        if not template:
            raise ValueError(
                f"Unknown prompt template: {name}. "
                f"Available: {list(cls._templates.keys())}"
            )
        return template

    @classmethod
    def register(cls, name: str, template: str):
        """Register a custom prompt template."""
        cls._templates[name] = template

    @classmethod
    def list_templates(cls) -> list:
        return list(cls._templates.keys())
