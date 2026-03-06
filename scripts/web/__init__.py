"""
FastAPI application factory for the LLM Gateway web UI and REST API.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .api import create_api_router
from .ui import create_ui_router


def create_app(config_manager, service_registry, repo_dir) -> FastAPI:
    """
    Build and return the FastAPI application.

    Args:
        config_manager:   scripts.config.manager.ConfigManager instance
        service_registry: scripts.services.ServiceRegistry instance
        repo_dir:         Path to the repository root
    """
    app = FastAPI(
        title="LLM Gateway",
        description="Local LLM routing gateway management interface",
        version="0.1.0",
        docs_url=None,       # disable Swagger UI
        redoc_url=None,      # disable ReDoc
    )

    # Store references for route handlers
    app.state.config_manager = config_manager
    app.state.service_registry = service_registry
    app.state.repo_dir = repo_dir

    # Read-only REST API
    app.include_router(
        create_api_router(),
        prefix="/api",
        tags=["api"],
    )

    # Web UI + action endpoints
    app.include_router(
        create_ui_router(),
        tags=["ui"],
    )

    # Global error handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        return JSONResponse(
            status_code=500,
            content={"error": str(exc)},
        )

    return app
