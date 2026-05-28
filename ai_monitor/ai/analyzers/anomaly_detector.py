# -*- coding: utf-8 -*-
"""Statistical anomaly detection without requiring LLM (zero cost)."""

from typing import Dict, List, Any
from datetime import datetime


class AnomalyDetector:
    """Detect anomalies based on statistical comparison with historical baseline."""

    async def detect(
        self,
        current_stats: Dict[str, Any],
        historical_baseline: Dict[str, Any],
    ) -> Dict:
        """Detect anomalies by comparing current stats against baseline.

        Args:
            current_stats: {"count": N, "avg_sentiment": X, "top_topics": [...]}
            historical_baseline: {"avg_count": N, "std_count": S, ...}

        Returns:
            {"is_anomaly": bool, "anomaly_score": float, "details": {...}}
        """
        if not historical_baseline:
            return {"is_anomaly": False, "anomaly_score": 0.0, "details": {}}

        details = {}
        anomaly_scores = []

        # Check volume anomaly
        current_count = current_stats.get("count", 0)
        avg_count = historical_baseline.get("avg_count", 0)
        std_count = historical_baseline.get("std_count", 1)

        if avg_count > 0 and std_count > 0:
            z_score = (current_count - avg_count) / max(std_count, 1)
            details["volume_z_score"] = z_score
            if abs(z_score) > 2.0:
                anomaly_scores.append(min(abs(z_score) / 5.0, 1.0))

        # Check sentiment shift
        current_sentiment = current_stats.get("avg_sentiment", 0.5)
        baseline_sentiment = historical_baseline.get("avg_sentiment", 0.5)
        sentiment_shift = abs(current_sentiment - baseline_sentiment)
        details["sentiment_shift"] = sentiment_shift
        if sentiment_shift > 0.3:
            anomaly_scores.append(sentiment_shift)

        max_score = max(anomaly_scores) if anomaly_scores else 0.0
        return {
            "is_anomaly": max_score > 0.3,
            "anomaly_score": max_score,
            "details": details,
        }
