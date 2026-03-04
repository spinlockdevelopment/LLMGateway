"""Token usage and cost tracking with SQLite persistence."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)

# Approximate cost per 1M tokens (input/output) for common models
# These are rough estimates; real costs come from provider response metadata when available.
COST_TABLE: dict[str, tuple[float, float]] = {
    # (input_per_1M, output_per_1M)
    "claude-3-opus": (15.0, 75.0),
    "claude-3-sonnet": (3.0, 15.0),
    "claude-3-haiku": (0.25, 1.25),
    "claude-3.5-sonnet": (3.0, 15.0),
    "claude-4-sonnet": (3.0, 15.0),
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.6),
    "gpt-4-turbo": (10.0, 30.0),
    "deepseek-chat": (0.14, 0.28),
    "mistral-small": (0.2, 0.6),
    "llama3-8b": (0.0, 0.0),  # local
    "llama3-70b": (0.0, 0.0),  # local
}


@dataclass
class UsageRecord:
    """A single usage event."""

    timestamp: float
    agent_id: str
    agent_name: str
    request_type: str
    pseudo_model: str
    selected_model: str
    provider: str
    tokens_in: int
    tokens_out: int
    estimated_cost: float
    latency_ms: float
    transaction_id: str = ""


class UsageTracker:
    """Tracks token usage and estimated costs in SQLite."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Create the database and tables."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self._db_path))
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                agent_id TEXT NOT NULL,
                agent_name TEXT NOT NULL DEFAULT '',
                request_type TEXT NOT NULL DEFAULT '',
                pseudo_model TEXT NOT NULL,
                selected_model TEXT NOT NULL,
                provider TEXT NOT NULL,
                tokens_in INTEGER NOT NULL,
                tokens_out INTEGER NOT NULL,
                estimated_cost REAL NOT NULL,
                latency_ms REAL NOT NULL,
                transaction_id TEXT NOT NULL DEFAULT ''
            )
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_usage_agent ON usage(agent_id)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_usage_timestamp ON usage(timestamp)
        """)
        await self._db.commit()
        logger.info("Usage tracker initialized at %s", self._db_path)

    async def record(self, record: UsageRecord) -> None:
        """Record a usage event."""
        if self._db is None:
            return
        await self._db.execute(
            """INSERT INTO usage
               (timestamp, agent_id, agent_name, request_type, pseudo_model,
                selected_model, provider, tokens_in, tokens_out, estimated_cost,
                latency_ms, transaction_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.timestamp,
                record.agent_id,
                record.agent_name,
                record.request_type,
                record.pseudo_model,
                record.selected_model,
                record.provider,
                record.tokens_in,
                record.tokens_out,
                record.estimated_cost,
                record.latency_ms,
                record.transaction_id,
            ),
        )
        await self._db.commit()

    async def query_usage(
        self,
        agent_id: str | None = None,
        since: float | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query usage records with optional filters."""
        if self._db is None:
            return []

        query = "SELECT * FROM usage WHERE 1=1"
        params: list[Any] = []

        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)
        if since:
            query += " AND timestamp >= ?"
            params.append(since)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        async with self._db.execute(query, params) as cursor:
            columns = [d[0] for d in cursor.description] if cursor.description else []
            rows = await cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]

    async def get_summary(self, agent_id: str | None = None) -> dict[str, Any]:
        """Get aggregate usage summary."""
        if self._db is None:
            return {}

        query = """
            SELECT
                agent_id,
                COUNT(*) as total_requests,
                SUM(tokens_in) as total_tokens_in,
                SUM(tokens_out) as total_tokens_out,
                SUM(estimated_cost) as total_cost,
                AVG(latency_ms) as avg_latency_ms
            FROM usage
        """
        params: list[Any] = []
        if agent_id:
            query += " WHERE agent_id = ?"
            params.append(agent_id)
        query += " GROUP BY agent_id"

        async with self._db.execute(query, params) as cursor:
            columns = [d[0] for d in cursor.description] if cursor.description else []
            rows = await cursor.fetchall()
            results = [dict(zip(columns, row)) for row in rows]

        return {"agents": results}

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    @staticmethod
    def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
        """Estimate cost in USD based on model and token counts."""
        # Try exact match first, then partial match
        costs = COST_TABLE.get(model)
        if costs is None:
            for key, val in COST_TABLE.items():
                if key in model.lower():
                    costs = val
                    break
        if costs is None:
            costs = (1.0, 2.0)  # default fallback

        input_cost = (tokens_in / 1_000_000) * costs[0]
        output_cost = (tokens_out / 1_000_000) * costs[1]
        return round(input_cost + output_cost, 6)
