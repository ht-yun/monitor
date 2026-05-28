# -*- coding: utf-8 -*-
"""Brand risk assessment using LLM."""

from ai_monitor.ai.base import AbstractAnalyzer, AIAnalysisResult, AbstractAIProvider
from ai_monitor.config.prompts import RISK_ASSESSMENT


class RiskAnalyzer(AbstractAnalyzer):
    """Assess brand risk for crawled content."""

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

        prompt = RISK_ASSESSMENT.format(text=text[:2000])
        try:
            result = await provider.chat_completion_json([
                {"role": "system", "content": "你是品牌舆情风险评估专家。请用JSON格式回复。"},
                {"role": "user", "content": prompt},
            ], temperature=0.1)
            return AIAnalysisResult(
                risk_score=float(result.get("risk_score", 0.0)),
                raw_response=str(result),
            )
        except Exception:
            return AIAnalysisResult()

    async def analyze_batch(
        self,
        items: list,
        provider: AbstractAIProvider,
    ) -> list:
        import asyncio

        tasks = [self.analyze(item, provider) for item in items]
        return await asyncio.gather(*tasks)
