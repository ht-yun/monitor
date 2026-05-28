# -*- coding: utf-8 -*-
"""OpenAI-compatible AI provider implementation."""

import json
from typing import Optional, AsyncIterator
from openai import AsyncOpenAI

from ai_monitor.ai.base import AbstractAIProvider
from ai_monitor.config.settings import get_settings


class OpenAIProvider(AbstractAIProvider):
    """OpenAI-compatible API provider (works with DeepSeek, Qwen, etc.)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        settings = get_settings()
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.base_url = base_url or settings.OPENAI_API_BASE
        self.default_model = model or settings.OPENAI_MODEL

        self._client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=settings.AI_REQUEST_TIMEOUT,
        )

    async def chat_completion(
        self,
        messages: list,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> str:
        response = await self._client.chat.completions.create(
            model=model or self.default_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""

    async def chat_completion_json(
        self,
        messages: list,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 512,
    ) -> dict:
        text = await self.chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return self._parse_json(text)

    async def chat_completion_stream(
        self,
        messages: list,
        model: Optional[str] = None,
    ) -> AsyncIterator[str]:
        stream = await self._client.chat.completions.create(
            model=model or self.default_model,
            messages=messages,
            temperature=0.3,
            max_tokens=1024,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    @staticmethod
    def _parse_json(text: str) -> dict:
        """Extract JSON from LLM response (handles markdown code fences)."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:]) if len(lines) > 1 else text
            if text.endswith("```"):
                text = text[:-3]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            import re
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            return {}
