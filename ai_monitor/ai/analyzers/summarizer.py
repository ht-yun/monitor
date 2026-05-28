# -*- coding: utf-8 -*-
"""Content summarizer using LLM."""

from ai_monitor.ai.base import AbstractAIProvider
from ai_monitor.config.prompts import BATCH_SUMMARY


class Summarizer:
    """Generate batch summaries from crawled content."""

    async def summarize_batch(
        self,
        items: list,
        platform: str,
        provider: AbstractAIProvider,
    ) -> dict:
        """Summarize a batch of content items."""
        if not items:
            return {"summary": "", "trends": [], "notable_items": []}

        posts_text = []
        for i, item in enumerate(items):
            title = item.get("title") or item.get("content", "")
            desc = item.get("desc") or ""
            posts_text.append(f"[{i}] {title} | {desc}")

        posts_str = "\n".join(posts_text)
        prompt = BATCH_SUMMARY.format(
            platform=platform,
            count=len(items),
            posts=posts_str[:4000],
        )

        try:
            result = await provider.chat_completion_json([
                {"role": "system", "content": "你是数据分析专家。请用JSON格式回复。"},
                {"role": "user", "content": prompt},
            ], temperature=0.3, max_tokens=800)
            return result
        except Exception:
            return {"summary": "", "trends": [], "notable_items": []}
