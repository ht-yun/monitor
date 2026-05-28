# -*- coding: utf-8 -*-
"""AI Provider factory - follows MediaCrawler's CacheFactory pattern."""

from typing import Dict, Type

from ai_monitor.ai.base import AbstractAIProvider


class AIProviderFactory:
    PROVIDERS: Dict[str, Type[AbstractAIProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_class: Type[AbstractAIProvider]):
        cls.PROVIDERS[name] = provider_class

    @classmethod
    def create(cls, provider_name: str, **kwargs) -> AbstractAIProvider:
        provider_class = cls.PROVIDERS.get(provider_name)
        if not provider_class:
            from ai_monitor.ai.providers.openai_provider import OpenAIProvider

            # Lazy-load OpenAI if not registered
            if provider_name == "openai":
                cls.register("openai", OpenAIProvider)
                return OpenAIProvider(**kwargs)
            raise ValueError(
                f"Unknown AI provider: {provider_name}. "
                f"Available: {list(cls.PROVIDERS.keys())}"
            )
        return provider_class(**kwargs)

    @classmethod
    def list_providers(cls) -> list:
        return list(cls.PROVIDERS.keys())
