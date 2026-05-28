# -*- coding: utf-8 -*-
"""Sentiment analysis implementation."""

from ai_monitor.ai.base import AbstractAnalyzer, AIAnalysisResult, AbstractAIProvider
from ai_monitor.config.prompts import SENTIMENT_ANALYSIS


class SentimentAnalyzer(AbstractAnalyzer):
    """Analyze sentiment of content using LLM."""

    async def analyze(
        self,
        content: dict,
        provider: AbstractAIProvider,
    ) -> AIAnalysisResult:
        title = content.get("title") or content.get("content", "")
        desc = content.get("desc") or content.get("content_text", "")
        text = f"{title}\n{desc}".strip()

        if not text:
            return AIAnalysisResult()

        prompt = SENTIMENT_ANALYSIS.format(text=text[:2000])
        try:
            result = await provider.chat_completion_json([
                {"role": "system", "content": "你是情感分析专家。请用JSON格式回复。"},
                {"role": "user", "content": prompt},
            ], temperature=0.1)
            return AIAnalysisResult(
                sentiment=result.get("sentiment", "neutral"),
                sentiment_score=float(result.get("score", 0.5)),
                raw_response=str(result),
            )
        except Exception:
            return AIAnalysisResult()
