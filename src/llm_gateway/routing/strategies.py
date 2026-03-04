"""Routing strategy implementations."""

from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class RouteTarget:
    """A resolved routing target."""

    model: str  # LiteLLM model identifier (e.g. "openrouter/anthropic/claude-3-opus")
    provider: str  # Provider name (e.g. "openrouter", "ollama", "openai")
    is_local: bool = False
    priority: int = 0
    weight: float = 1.0


@dataclass
class RouteDecision:
    """Result of a routing decision."""

    target: RouteTarget
    pseudo_model: str
    strategy: str
    fallbacks: list[RouteTarget] = field(default_factory=list)
    reason: str = ""


class PriorityStrategy:
    """Route to the highest-priority available target, with fallbacks."""

    @staticmethod
    def select(
        targets: list[RouteTarget],
        health: dict[str, bool] | None = None,
    ) -> RouteTarget | None:
        health = health or {}
        sorted_targets = sorted(targets, key=lambda t: t.priority)
        for t in sorted_targets:
            if health.get(t.model, True):
                return t
        return sorted_targets[0] if sorted_targets else None


class RoundRobinStrategy:
    """Rotate through targets sequentially."""

    def __init__(self) -> None:
        self._counters: dict[str, int] = {}

    def select(self, pseudo_model: str, targets: list[RouteTarget]) -> RouteTarget | None:
        if not targets:
            return None
        idx = self._counters.get(pseudo_model, 0)
        target = targets[idx % len(targets)]
        self._counters[pseudo_model] = idx + 1
        return target


class WeightedStrategy:
    """Select targets based on configured weights."""

    @staticmethod
    def select(targets: list[RouteTarget]) -> RouteTarget | None:
        if not targets:
            return None
        weights = [t.weight for t in targets]
        return random.choices(targets, weights=weights, k=1)[0]


class LocalFirstStrategy:
    """Prefer local models, fall back to remote if unavailable."""

    @staticmethod
    def select(
        targets: list[RouteTarget],
        health: dict[str, bool] | None = None,
    ) -> RouteTarget | None:
        health = health or {}
        local = [t for t in targets if t.is_local]
        remote = [t for t in targets if not t.is_local]

        for t in local:
            if health.get(t.model, True):
                return t
        for t in remote:
            if health.get(t.model, True):
                return t
        return targets[0] if targets else None
