"""Core routing engine that resolves pseudo-models to actual provider targets."""

from __future__ import annotations

import logging
from typing import Any

from llm_gateway.routing.strategies import (
    LocalFirstStrategy,
    PriorityStrategy,
    RouteDecision,
    RouteTarget,
    RoundRobinStrategy,
    WeightedStrategy,
)

logger = logging.getLogger(__name__)

# Models known to be local runtimes
LOCAL_PREFIXES = ("ollama/", "ollama_chat/", "mlx/", "llamacpp/")


def _is_local(model: str) -> bool:
    return any(model.startswith(p) for p in LOCAL_PREFIXES)


def _provider_from_model(model: str) -> str:
    """Extract provider name from a LiteLLM model string."""
    if "/" in model:
        return model.split("/")[0]
    return "unknown"


class RoutingEngine:
    """Resolves pseudo-model names to concrete LiteLLM model targets."""

    def __init__(self) -> None:
        self._pseudo_models: dict[str, dict[str, Any]] = {}
        self._round_robin = RoundRobinStrategy()

    def load_config(self, routing_config: dict[str, Any]) -> None:
        """Load routing configuration from parsed YAML."""
        self._pseudo_models = routing_config.get("pseudo_models", {})
        logger.info("Loaded %d pseudo-model routes", len(self._pseudo_models))

    def resolve(
        self,
        model: str,
        *,
        agent: str | None = None,
        request_type: str | None = None,
        health: dict[str, bool] | None = None,
    ) -> RouteDecision:
        """Resolve a model name (pseudo or real) to a routing decision.

        If the model is a known pseudo-model, apply the configured routing strategy.
        Otherwise, pass the model through as-is (direct model request).
        """
        if model in self._pseudo_models:
            return self._resolve_pseudo(model, health=health)

        # Direct model pass-through
        target = RouteTarget(
            model=model,
            provider=_provider_from_model(model),
            is_local=_is_local(model),
        )
        return RouteDecision(
            target=target,
            pseudo_model=model,
            strategy="passthrough",
            reason=f"Direct model request: {model}",
        )

    def _resolve_pseudo(
        self,
        pseudo: str,
        health: dict[str, bool] | None = None,
    ) -> RouteDecision:
        cfg = self._pseudo_models[pseudo]

        # Build target list from config
        targets: list[RouteTarget] = []
        fallbacks: list[RouteTarget] = []
        strategy_name = "priority"

        if "round_robin" in cfg:
            strategy_name = "round_robin"
            for i, m in enumerate(cfg["round_robin"]):
                targets.append(RouteTarget(
                    model=m, provider=_provider_from_model(m),
                    is_local=_is_local(m), priority=i,
                ))

        elif "weighted" in cfg:
            strategy_name = "weighted"
            for entry in cfg["weighted"]:
                targets.append(RouteTarget(
                    model=entry["model"],
                    provider=_provider_from_model(entry["model"]),
                    is_local=_is_local(entry["model"]),
                    weight=entry.get("weight", 1.0),
                ))

        elif "local_first" in cfg:
            strategy_name = "local_first"
            local_models = cfg["local_first"]
            if isinstance(local_models, str):
                local_models = [local_models]
            for m in local_models:
                targets.append(RouteTarget(
                    model=m, provider=_provider_from_model(m),
                    is_local=_is_local(m), priority=0,
                ))
            if "fallback" in cfg:
                fb_models = cfg["fallback"] if isinstance(cfg["fallback"], list) else [cfg["fallback"]]
                for m in fb_models:
                    t = RouteTarget(
                        model=m, provider=_provider_from_model(m),
                        is_local=_is_local(m), priority=10,
                    )
                    targets.append(t)
                    fallbacks.append(t)

        else:
            # Priority-based: primary + fallback
            if "primary" in cfg:
                targets.append(RouteTarget(
                    model=cfg["primary"],
                    provider=_provider_from_model(cfg["primary"]),
                    is_local=_is_local(cfg["primary"]),
                    priority=0,
                ))
            if "local_model" in cfg:
                targets.append(RouteTarget(
                    model=cfg["local_model"],
                    provider=_provider_from_model(cfg["local_model"]),
                    is_local=True,
                    priority=0,
                ))
            if "fallback" in cfg:
                fb_models = cfg["fallback"] if isinstance(cfg["fallback"], list) else [cfg["fallback"]]
                for i, m in enumerate(fb_models):
                    t = RouteTarget(
                        model=m, provider=_provider_from_model(m),
                        is_local=_is_local(m), priority=i + 1,
                    )
                    targets.append(t)
                    fallbacks.append(t)

        # Select target using strategy
        selected: RouteTarget | None = None
        if strategy_name == "round_robin":
            selected = self._round_robin.select(pseudo, targets)
        elif strategy_name == "weighted":
            selected = WeightedStrategy.select(targets)
        elif strategy_name == "local_first":
            selected = LocalFirstStrategy.select(targets, health=health)
        else:
            selected = PriorityStrategy.select(targets, health=health)

        if selected is None:
            raise ValueError(f"No available targets for pseudo-model '{pseudo}'")

        remaining_fallbacks = [t for t in fallbacks if t.model != selected.model]

        return RouteDecision(
            target=selected,
            pseudo_model=pseudo,
            strategy=strategy_name,
            fallbacks=remaining_fallbacks,
            reason=f"Routed '{pseudo}' via {strategy_name} -> {selected.model}",
        )

    def list_pseudo_models(self) -> list[dict[str, Any]]:
        """Return list of configured pseudo-models for the /v1/models endpoint."""
        models = []
        for name, cfg in self._pseudo_models.items():
            models.append({
                "id": name,
                "object": "model",
                "owned_by": "llm-gateway",
                "config": cfg,
            })
        return models
