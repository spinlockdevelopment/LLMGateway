"""GET /v1/models — list available pseudo-models and pass-through models."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/v1/models")
async def list_models(request: Request) -> dict[str, Any]:
    """List all available pseudo-models defined in routing config."""
    routing_engine = request.app.state.routing_engine
    local_manager = request.app.state.local_manager

    pseudo_models = routing_engine.list_pseudo_models()

    # Also include locally-available models
    try:
        ollama_models = await local_manager.list_ollama_models()
        for m in ollama_models:
            pseudo_models.append({
                "id": f"ollama/{m.get('name', '')}",
                "object": "model",
                "owned_by": "local-ollama",
            })
    except Exception:
        pass

    return {
        "object": "list",
        "data": pseudo_models,
    }
