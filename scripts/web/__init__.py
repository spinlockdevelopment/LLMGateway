"""
FastAPI application factory for the LLM Gateway web UI and REST API.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .api import create_api_router
from .ui import create_ui_router


def create_app(config_manager, dmr, whisper, llmfit, repo_dir, data_dir=None) -> FastAPI:
    """
    Build and return the FastAPI application.

    Args:
        config_manager:   scripts.config.manager.ConfigManager instance
        dmr:              scripts.services.docker_model_runner.DockerModelRunner instance
        whisper:          scripts.services.whisper_manager.WhisperManager instance
        llmfit:           scripts.services.llmfit.LlmfitClient instance
        repo_dir:         Path to the repository root (code, .env.example)
        data_dir:         Path to the data directory (.env, user config, logs).
                          Defaults to repo_dir for backward compatibility.
    """
    app = FastAPI(
        title="LLM Gateway",
        description="Local LLM routing gateway management interface",
        version="0.2.0",
        docs_url=None,       # disable Swagger UI
        redoc_url=None,      # disable ReDoc
    )

    # Store references for route handlers
    app.state.config_manager = config_manager
    app.state.dmr = dmr
    app.state.whisper = whisper
    app.state.llmfit = llmfit
    app.state.repo_dir = repo_dir
    app.state.data_dir = data_dir or repo_dir

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
