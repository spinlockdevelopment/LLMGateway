"""Simple in-memory token-bucket rate limiter."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""

    capacity: float
    rate: float  # tokens per second
    tokens: float = 0.0
    last_refill: float = field(default_factory=time.monotonic)

    def consume(self, n: float = 1.0) -> bool:
        """Try to consume n tokens. Returns True if allowed."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_refill = now

        if self.tokens >= n:
            self.tokens -= n
            return True
        return False


class RateLimiter:
    """Per-agent rate limiter using token buckets."""

    def __init__(self, default_rpm: int = 60, burst: int = 10) -> None:
        self._default_rpm = default_rpm
        self._burst = burst
        self._buckets: dict[str, TokenBucket] = {}

    def check(self, agent_id: str, rpm_override: int | None = None) -> bool:
        """Check if a request from agent_id is allowed."""
        if agent_id not in self._buckets:
            rpm = rpm_override or self._default_rpm
            self._buckets[agent_id] = TokenBucket(
                capacity=float(self._burst),
                rate=rpm / 60.0,
                tokens=float(self._burst),
            )
        return self._buckets[agent_id].consume()
