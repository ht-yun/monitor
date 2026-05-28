# -*- coding: utf-8 -*-
"""Abstract base classes for AI providers and analyzers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, AsyncIterator


@dataclass
class AIAnalysisResult:
    """Result of analyzing a single piece of content."""

    sentiment: str = "neutral"  # positive | negative | neutral
    sentiment_score: float = 0.5  # 0.0 (negative) to 1.0 (positive)
    topics: list = field(default_factory=list)
    entities: list = field(default_factory=list)
    summary: str = ""
    risk_score: float = 0.0
    raw_response: str = ""


@dataclass
class BatchAnalysisResult:
    """Result of batch analysis."""

    items: list = field(default_factory=list)  # list of per-item AIAnalysisResult
    batch_summary: str = ""
    trends: list = field(default_factory=list)
    anomalies: list = field(default_factory=list)
    total_items: int = 0


class AbstractAIProvider(ABC):
    """Abstract AI provider (LLM API client)."""

    @abstractmethod
    async def chat_completion(
        self,
        messages: list,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> str:
        """Send chat completion request, return response text."""

    @abstractmethod
    async def chat_completion_json(
        self,
        messages: list,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 512,
    ) -> dict:
        """Send chat completion request, parse response as JSON."""

    @abstractmethod
    async def chat_completion_stream(
        self,
        messages: list,
        model: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """Stream chat completion response."""


class AbstractAnalyzer(ABC):
    """Abstract content analyzer."""

    @abstractmethod
    async def analyze(
        self,
        content: dict,
        provider: AbstractAIProvider,
    ) -> AIAnalysisResult:
        """Analyze a single content item."""

    async def analyze_batch(
        self,
        items: list,
        provider: AbstractAIProvider,
        chunk_size: int = 10,
        rate_limit_delay: float = 0.5,
    ) -> list:
        """Analyze a batch of items with rate limiting."""
        results = []
        import asyncio
        for i in range(0, len(items), chunk_size):
            chunk = items[i: i + chunk_size]
            chunk_results = await asyncio.gather(
                *[self.analyze(item, provider) for item in chunk],
                return_exceptions=True,
            )
            for r in chunk_results:
                if isinstance(r, Exception):
                    results.append(AIAnalysisResult())
                else:
                    results.append(r)
            if i + chunk_size < len(items):
                await asyncio.sleep(rate_limit_delay)
        return results
