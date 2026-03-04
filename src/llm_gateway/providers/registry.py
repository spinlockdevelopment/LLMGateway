"""Provider registry — manages provider adapters and health state."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from llm_gateway.providers.base import ProviderAdapter
from llm_gateway.providers.litellm_adapter import LiteLLMAdapter

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Registry of available provider adapters and their health status."""

    def __init__(self) -> None:
        self._adapters: dict[str, ProviderAdapter] = {}
        self._health: dict[str, bool] = {}
        self._health_task: asyncio.Task | None = None

    def register(self, name: str, adapter: ProviderAdapter) -> None:
        self._adapters[name] = adapter
        self._health[name] = True
        logger.info("Registered provider: %s", name)

    def get(self, name: str) -> ProviderAdapter | None:
        return self._adapters.get(name)

    def get_default(self) -> LiteLLMAdapter:
        """Return the default LiteLLM adapter (handles all providers)."""
        adapter = self._adapters.get("litellm")
        if adapter is None:
            raise RuntimeError("LiteLLM adapter not registered")
        return adapter  # type: ignore[return-value]

    @property
    def health(self) -> dict[str, bool]:
        return dict(self._health)

    def load_config(self, providers_config: dict[str, Any], settings: Any) -> None:
        """Initialize adapters from providers config + settings."""
        # The primary adapter is LiteLLM, which handles all providers
        litellm_config = {
            "openrouter_api_key": settings.openrouter_api_key,
            "openai_api_key": settings.openai_api_key,
            "anthropic_api_key": settings.anthropic_api_key,
            "google_api_key": settings.google_api_key,
            "request_timeout": providers_config.get("default_timeout", 120),
        }
        self.register("litellm", LiteLLMAdapter(litellm_config))

    async def start_health_checks(self, interval: int = 60) -> None:
        """Periodically check provider health."""
        async def _loop() -> None:
            while True:
                for name, adapter in self._adapters.items():
                    try:
                        self._health[name] = await adapter.health_check()
                    except Exception:
                        self._health[name] = False
                await asyncio.sleep(interval)

        self._health_task = asyncio.create_task(_loop())

    async def stop_health_checks(self) -> None:
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
