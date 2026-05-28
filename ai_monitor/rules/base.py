# -*- coding: utf-8 -*-
"""Abstract base class for monitoring rules."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RuleConfigModel(BaseModel):
    """Configuration for a monitoring rule."""

    rule_id: str = ""
    name: str
    rule_type: str  # keyword | sentiment | anomaly | trend
    description: str = ""
    params: Dict[str, Any] = Field(default_factory=dict)
    severity: str = "warning"  # info | warning | critical
    notification_channels: List[str] = Field(default_factory=list)
    cooldown_minutes: int = 30
    platform: Optional[str] = None  # None = all platforms


class RuleEvaluationResult(BaseModel):
    """Result of a single rule evaluation."""

    rule_id: str
    rule_name: str
    rule_type: str
    triggered: bool = False
    severity: str = "warning"
    matched_items: List[Dict] = Field(default_factory=list)
    summary: str = ""  # Chinese description of what triggered
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)
    metric_value: Optional[float] = None
    threshold: Optional[float] = None


class AbstractMonitorRule(ABC):
    """Abstract monitoring rule.

    Subclass and register via RuleRegistry.
    """

    def __init__(self, config: RuleConfigModel):
        self.config = config

    @abstractmethod
    async def evaluate(
        self,
        content_items: List[Dict],
        analysis_results: List[Dict],
        historical_data: Optional[List[Dict]] = None,
    ) -> RuleEvaluationResult:
        """Evaluate whether this rule is triggered.

        Args:
            content_items: Raw crawled content
            analysis_results: AI analysis outputs for each content item
            historical_data: Historical analysis results for trend comparison

        Returns:
            RuleEvaluationResult with triggered=True and matched_items if triggered.
        """

    def get_config(self) -> RuleConfigModel:
        return self.config
