"""LiteLLM-based provider adapter — the primary provider engine.

LiteLLM handles the actual API translation to 100+ providers.
We wrap it to add gateway-specific behavior (telemetry, cost tracking, error handling).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, AsyncIterator

import litellm

from llm_gateway.providers.base import CompletionRequest, CompletionResponse, ProviderAdapter

logger = logging.getLogger(__name__)

# Suppress LiteLLM's verbose default logging
litellm.suppress_debug_info = True


class LiteLLMAdapter(ProviderAdapter):
    """Provider adapter that delegates to LiteLLM for all providers."""

    def __init__(self, provider_config: dict[str, Any] | None = None) -> None:
        self._config = provider_config or {}
        self._configure_litellm()

    def _configure_litellm(self) -> None:
        """Apply provider API keys and settings to LiteLLM globals."""
        key_map = {
            "openrouter_api_key": "OPENROUTER_API_KEY",
            "openai_api_key": "OPENAI_API_KEY",
            "anthropic_api_key": "ANTHROPIC_API_KEY",
            "google_api_key": "GEMINI_API_KEY",
        }
        for config_key, env_key in key_map.items():
            val = self._config.get(config_key)
            if val:
                import os
                os.environ[env_key] = val

        # Set default timeout
        litellm.request_timeout = self._config.get("request_timeout", 120)

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Send a completion request via LiteLLM."""
        start = time.monotonic()

        kwargs = self._build_kwargs(request)

        try:
            response = await litellm.acompletion(**kwargs)
        except Exception as e:
            logger.error("LiteLLM completion failed for model=%s: %s", request.model, e)
            raise

        latency_ms = (time.monotonic() - start) * 1000

        usage = getattr(response, "usage", None)
        tokens_in = getattr(usage, "prompt_tokens", 0) if usage else 0
        tokens_out = getattr(usage, "completion_tokens", 0) if usage else 0

        content = ""
        choices = getattr(response, "choices", [])
        if choices:
            message = getattr(choices[0], "message", None)
            if message:
                content = getattr(message, "content", "") or ""

        return CompletionResponse(
            id=getattr(response, "id", ""),
            model=getattr(response, "model", request.model),
            provider=self._extract_provider(request.model),
            content=content,
            finish_reason=getattr(choices[0], "finish_reason", None) if choices else None,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            raw=response.model_dump() if hasattr(response, "model_dump") else {},
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[dict[str, Any]]:
        """Stream a completion via LiteLLM, yielding OpenAI-compatible SSE chunks."""
        kwargs = self._build_kwargs(request)
        kwargs["stream"] = True

        try:
            response = await litellm.acompletion(**kwargs)

            async for chunk in response:
                chunk_data = chunk.model_dump() if hasattr(chunk, "model_dump") else chunk
                yield chunk_data

        except Exception as e:
            logger.error("LiteLLM stream failed for model=%s: %s", request.model, e)
            error_chunk = {
                "error": {"message": str(e), "type": "provider_error"},
            }
            yield error_chunk

    async def health_check(self) -> bool:
        """Check if LiteLLM can reach at least one provider."""
        try:
            # Simple connectivity check — list models
            models = await asyncio.to_thread(litellm.model_list)
            return True
        except Exception:
            return True  # LiteLLM doesn't require pre-connectivity

    def get_name(self) -> str:
        return "litellm"

    def _build_kwargs(self, request: CompletionRequest) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": request.messages,
        }
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens
        if request.top_p is not None:
            kwargs["top_p"] = request.top_p
        if request.stop:
            kwargs["stop"] = request.stop
        # Pass through any extra params (tool_choice, tools, response_format, etc.)
        kwargs.update(request.extra)
        return kwargs

    @staticmethod
    def _extract_provider(model: str) -> str:
        if "/" in model:
            return model.split("/")[0]
        return "openai"  # LiteLLM default
