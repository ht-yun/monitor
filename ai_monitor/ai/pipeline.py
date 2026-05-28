# -*- coding: utf-8 -*-
"""AI Pipeline - orchestrates multiple analyzers in sequence."""

import asyncio
from datetime import datetime
from typing import Dict, List, Any

from ai_monitor.ai.base import AbstractAIProvider, AbstractAnalyzer
from ai_monitor.ai.analyzers.sentiment_analyzer import SentimentAnalyzer
from ai_monitor.ai.analyzers.topic_analyzer import TopicAnalyzer
from ai_monitor.ai.analyzers.summarizer import Summarizer
from ai_monitor.ai.analyzers.anomaly_detector import AnomalyDetector
from ai_monitor.ai.analyzers.risk_analyzer import RiskAnalyzer


class AIPipeline:
    """Orchestrates the full AI analysis pipeline on crawled content."""

    def __init__(self, provider: AbstractAIProvider):
        self.provider = provider
        self.sentiment_analyzer = SentimentAnalyzer()
        self.topic_analyzer = TopicAnalyzer()
        self.summarizer = Summarizer()
        self.anomaly_detector = AnomalyDetector()
        self.risk_analyzer = RiskAnalyzer()

    async def process(
        self,
        items: List[Dict],
        platform: str,
        job_id: str,
        historical_baseline: Dict = None,
    ) -> Dict:
        """Run full analysis pipeline on crawled items.

        Args:
            items: List of crawled content items
            platform: Platform name
            job_id: Monitoring job ID
            historical_baseline: Historical stats for anomaly detection

        Returns:
            Dict with analysis results
        """
        if not items:
            return {"items": [], "summary": "", "anomalies": {}, "total_analyzed": 0}

        # Run sentiment and topic analysis concurrently
        sentiment_task = self.sentiment_analyzer.analyze_batch(items, self.provider)
        topic_task = self.topic_analyzer.analyze_batch(items, self.provider)
        risk_task = self.risk_analyzer.analyze_batch(items, self.provider)

        sentiments, topics, risks = await asyncio.gather(
            sentiment_task, topic_task, risk_task
        )

        # Merge per-item results
        results = []
        positive_count = 0
        negative_count = 0
        neutral_count = 0

        for i, item in enumerate(items):
            content_id = (
                item.get("note_id")
                or item.get("video_id")
                or item.get("aweme_id")
                or item.get("content_id")
                or f"item_{i}"
            )
            s = sentiments[i] if i < len(sentiments) else None
            t = topics[i] if i < len(topics) else None
            rk = risks[i] if i < len(risks) else None

            sentiment_val = s.sentiment if s else "neutral"
            if sentiment_val == "positive":
                positive_count += 1
            elif sentiment_val == "negative":
                negative_count += 1
            else:
                neutral_count += 1

            results.append({
                "content_id": content_id,
                "platform": platform,
                "job_id": job_id,
                "content_type": item.get("content_type", "note"),
                "sentiment": sentiment_val,
                "sentiment_score": s.sentiment_score if s else 0.5,
                "topics": t.topics if t else [],
                "entities": t.entities if t else [],
                "risk_score": (
                    rk.risk_score if rk and rk.risk_score
                    else (s.risk_score if s else 0.0)
                ),
                "raw_content": (
                    (item.get("title", "") + " " + item.get("desc", ""))[:2000]
                ),
                "analyzed_at": datetime.utcnow().isoformat(),
            })

        # Batch summary
        batch_summary = await self.summarizer.summarize_batch(
            items, platform, self.provider
        )

        # Current stats for anomaly detection
        total = len(items)
        current_stats = {
            "count": total,
            "avg_sentiment": (
                (positive_count * 1 + neutral_count * 0.5 + negative_count * 0) / total
                if total > 0
                else 0.5
            ),
            "negative_ratio": negative_count / total if total > 0 else 0,
            "positive_ratio": positive_count / total if total > 0 else 0,
            "all_topics": list(set(
                t for item in results for t in item.get("topics", [])
            )),
        }

        anomalies = {}
        if historical_baseline:
            anomalies = await self.anomaly_detector.detect(
                current_stats, historical_baseline
            )

        return {
            "items": results,
            "summary": batch_summary.get("summary", ""),
            "trends": batch_summary.get("trends", []),
            "notable_items": batch_summary.get("notable_items", []),
            "anomalies": anomalies,
            "current_stats": current_stats,
            "total_analyzed": len(results),
        }
