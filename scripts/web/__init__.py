"""
FastAPI application factory for the LLM Gateway web UI and REST API.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import create_api_router
from .ui import create_ui_router

_STATIC_DIR = Path(__file__).parent / "static"


def _same_origin(request) -> bool:
    site = request.headers.get("sec-fetch-site")
    if site is not None:
        return site in ("same-origin", "none")
    origin = request.headers.get("origin")
    if origin is None:
        return True
    hosts = {request.headers.get("host"), request.headers.get("x-forwarded-host")}
    return urlsplit(origin).netloc in hosts


def create_app(config_manager, service_registry, repo_dir, data_dir=None) -> FastAPI:
    """
    Build and return the FastAPI application.

    Args:
        config_manager:   scripts.config.manager.ConfigManager instance
        service_registry: scripts.services.ServiceRegistry instance
        repo_dir:         Path to the repository root (code, .env.example)
        data_dir:         Path to the data directory (.env, user config, logs).
                          Defaults to repo_dir for backward compatibility.
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

    # Static assets (app icon, favicons)
    if _STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    # CSRF guard: the dashboard has no auth, so a page on another origin must
    # not be able to drive it. Browsers mark cross-origin requests with
    # Sec-Fetch-Site (Origin as fallback); curl/gw send neither and pass.
    @app.middleware("http")
    async def same_origin_only(request, call_next):
        unsafe = request.method not in ("GET", "HEAD", "OPTIONS") \
            or request.url.path.startswith("/ui/dmr/pull")  # GET that pulls models
        if unsafe and not _same_origin(request):
            return JSONResponse(status_code=403, content={"error": "cross-origin request refused"})
        return await call_next(request)

    # Global error handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        return JSONResponse(
            status_code=500,
            content={"error": str(exc)},
        )

    return app
