"""Admin API endpoints for gateway management."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/admin")


@router.get("/status")
async def status(request: Request) -> dict[str, Any]:
    """Get gateway status including local model state and provider health."""
    local_manager = request.app.state.local_manager
    provider_registry = request.app.state.provider_registry

    local_status = await local_manager.status()

    return {
        "status": "running",
        "timestamp": time.time(),
        "local_models": local_status,
        "provider_health": provider_registry.health,
    }


@router.post("/set-model")
async def set_model(request: Request) -> dict[str, Any]:
    """Load or swap a local model.

    Body: {"model": "llama3-8b", "action": "load"|"unload"}
    """
    body = await request.json()
    model_name = body.get("model")
    action = body.get("action", "load")

    if not model_name:
        raise HTTPException(status_code=400, detail="Missing 'model' field")

    local_manager = request.app.state.local_manager

    if action == "load":
        result = await local_manager.load_model(model_name)
    elif action == "unload":
        result = await local_manager.unload_model(model_name)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/reload-config")
async def reload_config(request: Request) -> dict[str, Any]:
    """Reload all configuration files from disk."""
    config_manager = request.app.state.config_manager
    config_manager.reload()
    return {"status": "reloaded", "timestamp": time.time()}


@router.get("/usage")
async def usage(request: Request, agent: str | None = None, limit: int = 100) -> dict[str, Any]:
    """Query usage records, optionally filtered by agent."""
    usage_tracker = request.app.state.usage_tracker
    records = await usage_tracker.query_usage(agent_id=agent, limit=limit)
    summary = await usage_tracker.get_summary(agent_id=agent)
    return {
        "summary": summary,
        "records": records,
    }


@router.get("/models")
async def admin_models(request: Request) -> dict[str, Any]:
    """List all configured models (pseudo + local)."""
    routing_engine = request.app.state.routing_engine
    local_manager = request.app.state.local_manager

    return {
        "pseudo_models": routing_engine.list_pseudo_models(),
        "local_models": (await local_manager.status()).get("models", {}),
    }


@router.get("/health")
async def health() -> dict[str, str]:
    """Simple health check endpoint."""
    return {"status": "ok"}
