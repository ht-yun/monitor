# -*- coding: utf-8 -*-
"""Topic/keyword extraction analyzer."""

from ai_monitor.ai.base import AbstractAnalyzer, AIAnalysisResult, AbstractAIProvider
from ai_monitor.config.prompts import TOPIC_EXTRACTION


class TopicAnalyzer(AbstractAnalyzer):
    """Extract topics, keywords, and named entities from content."""

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

        prompt = TOPIC_EXTRACTION.format(text=text[:2000])
        try:
            result = await provider.chat_completion_json([
                {"role": "system", "content": "你是文本分析专家。请用JSON格式回复。"},
                {"role": "user", "content": prompt},
            ], temperature=0.2)
            return AIAnalysisResult(
                topics=result.get("topics", []),
                entities=result.get("entities", []),
                raw_response=str(result),
            )
        except Exception:
            return AIAnalysisResult()
