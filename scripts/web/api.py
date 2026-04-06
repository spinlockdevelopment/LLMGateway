"""
Read-only REST API for programmatic status queries.

All endpoints are GET-only. This is the public API surface for
external tools and scripts to check gateway health and service status.

Endpoints:
    GET /api/health                  — liveness probe (always 200)
    GET /api/status                  — full system overview including DMR and whisper
    GET /api/config                  — current config (secrets masked)
    GET /api/dmr/status              — DMR availability and model count
    GET /api/models                  — list pulled DMR models
    GET /api/llmfit/recommendations  — model recommendations from llmfit
    GET /api/llmfit/system           — hardware info from llmfit
"""

from __future__ import annotations

import platform
import sys
import time

import psutil
from fastapi import APIRouter, Request
from services.llmfit import INSTALL_COMMAND
from services.status import get_full_status


_start_time = time.time()


async def _get_dmr_status(dmr) -> tuple[list[dict], bool]:
    """Fetch DMR models and availability in a single pass.

    list_models() already hits GET /models — if it returns results the
    endpoint is reachable; an empty list means either "no models" or
    "unreachable", so we fall back to is_available() only when empty.
    """
    models = await dmr.list_models()
    available = bool(models) or await dmr.is_available()
    return models, available


def create_api_router() -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    async def health():
        """Liveness probe — always returns 200 if the gateway is running."""
        return {"status": "ok"}

    @router.get("/status")
    async def status(request: Request):
        """Full system overview: platform, memory, DMR status, whisper status."""
        dmr = request.app.state.dmr
        whisper = request.app.state.whisper
        mem = psutil.virtual_memory()

        dmr_models, dmr_available = await _get_dmr_status(dmr)

        return {
            "gateway": {
                "uptime_sec": round(time.time() - _start_time, 1),
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "architecture": platform.machine(),
            },
            "memory": {
                "total_gb": round(mem.total / (1024 ** 3), 1),
                "used_gb": round(mem.used / (1024 ** 3), 1),
                "available_gb": round(mem.available / (1024 ** 3), 1),
                "percent": mem.percent,
            },
            "dmr": dmr.status_dict(available=dmr_available, models_count=len(dmr_models)),
            "whisper": whisper.status_dict(),
        }

    @router.get("/status/full")
    async def full_status(request: Request):
        """Full system status matching gw CLI output: components, paths, accounts."""
        repo_dir = request.app.state.repo_dir
        data_dir = request.app.state.data_dir
        return await get_full_status(repo_dir, data_dir)

    @router.get("/config")
    async def get_config(request: Request):
        """Return current config with secret values masked."""
        cm = request.app.state.config_manager
        return cm.get_config_masked()

    @router.get("/dmr/status")
    async def dmr_status(request: Request):
        """DMR availability and model count."""
        dmr = request.app.state.dmr
        models, available = await _get_dmr_status(dmr)
        return dmr.status_dict(available=available, models_count=len(models))

    @router.get("/models")
    async def list_models(request: Request):
        """List pulled DMR models."""
        dmr = request.app.state.dmr
        models = await dmr.list_models()
        return {"models": models}

    @router.get("/llmfit/recommendations")
    async def llmfit_recommendations(
        request: Request,
        use_case: str | None = None,
        limit: int = 5,
    ):
        """Query llmfit for model recommendations."""
        llmfit = request.app.state.llmfit
        if not llmfit.is_installed():
            return {
                "installed": False,
                "recommendations": [],
                "install_hint": INSTALL_COMMAND,
            }
        recommendations = await llmfit.recommend(use_case=use_case, limit=limit)
        return {"installed": True, "recommendations": recommendations}

    @router.get("/llmfit/system")
    async def llmfit_system(request: Request):
        """Hardware info from llmfit."""
        llmfit = request.app.state.llmfit
        info = await llmfit.system_info()
        return {"system": info}

    return router
