"""Provider adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


@dataclass
class CompletionRequest:
    """Normalized completion request."""

    model: str
    messages: list[dict[str, Any]]
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    stop: list[str] | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompletionResponse:
    """Normalized completion response."""

    id: str
    model: str
    provider: str
    content: str
    finish_reason: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0
    raw: dict[str, Any] = field(default_factory=dict)


class ProviderAdapter(ABC):
    """Base interface for LLM provider adapters."""

    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Send a completion request and return the response."""

    @abstractmethod
    async def stream(self, request: CompletionRequest) -> AsyncIterator[dict[str, Any]]:
        """Stream a completion request, yielding SSE-compatible chunks."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is reachable and healthy."""

    @abstractmethod
    def get_name(self) -> str:
        """Return the provider name."""
