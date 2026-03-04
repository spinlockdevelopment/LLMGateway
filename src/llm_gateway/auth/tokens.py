"""Gateway API token authentication and agent identification."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


@dataclass
class AgentIdentity:
    """Resolved agent identity from a gateway token."""

    token: str
    agent_id: str
    agent_name: str
    rate_limit_rpm: int
    allowed_models: list[str]  # empty = all allowed
    metadata: dict[str, str]


class TokenAuth:
    """Manages gateway API tokens and agent identification."""

    def __init__(self) -> None:
        self._tokens: dict[str, dict[str, Any]] = {}

    def load_config(self, agents_config: dict[str, Any]) -> None:
        """Load agent tokens from config."""
        agents = agents_config.get("agents", {})
        self._tokens.clear()
        for agent_id, cfg in agents.items():
            token = cfg.get("token", "")
            if token:
                self._tokens[token] = {"agent_id": agent_id, **cfg}
        logger.info("Loaded %d agent tokens", len(self._tokens))

    def authenticate(self, request: Request) -> AgentIdentity:
        """Authenticate a request and return agent identity.

        Raises HTTPException 401 if token is invalid.
        """
        auth_header = request.headers.get("authorization", "")
        if not auth_header.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

        token = auth_header[7:].strip()

        agent_cfg = self._tokens.get(token)
        if agent_cfg is None:
            raise HTTPException(status_code=401, detail="Invalid gateway token")

        # Extract optional headers
        metadata = {}
        for header in ("x-agent-name", "x-request-type", "x-transaction-id"):
            val = request.headers.get(header)
            if val:
                metadata[header] = val

        return AgentIdentity(
            token=token,
            agent_id=agent_cfg.get("agent_id", "unknown"),
            agent_name=metadata.get("x-agent-name", agent_cfg.get("name", agent_cfg.get("agent_id", "unknown"))),
            rate_limit_rpm=agent_cfg.get("rate_limit_rpm", 60),
            allowed_models=agent_cfg.get("allowed_models", []),
            metadata=metadata,
        )

    def is_model_allowed(self, agent: AgentIdentity, model: str) -> bool:
        """Check if an agent is allowed to use a model."""
        if not agent.allowed_models:
            return True  # no restrictions
        return model in agent.allowed_models
