"""
Read-only REST API for programmatic status queries.

All endpoints are GET-only. This is the public API surface for
external tools and scripts to check gateway health and service status.

Endpoints:
    GET /api/health         — liveness probe (always 200)
    GET /api/status         — full system overview
    GET /api/services       — all managed services
    GET /api/services/{name} — single service detail
    GET /api/config         — current config (secrets masked)
    GET /api/memory         — system memory usage
"""

from __future__ import annotations

import platform
import sys
import time

import psutil
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse


_start_time = time.time()


def create_api_router() -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    async def health():
        """Liveness probe — always returns 200 if the gateway is running."""
        return {"status": "ok"}

    @router.get("/status")
    async def status(request: Request):
        """Full system overview: platform, memory, services, uptime."""
        registry = request.app.state.service_registry
        mem = psutil.virtual_memory()

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
            "services": registry.all_status(),
        }

    @router.get("/services")
    async def list_services(request: Request):
        """List all managed services with their current state."""
        registry = request.app.state.service_registry
        return {"services": registry.all_status()}

    @router.get("/services/{name}")
    async def get_service(name: str, request: Request):
        """Get status of a single service by name."""
        registry = request.app.state.service_registry
        svc = registry.get(name)
        if svc is None:
            raise HTTPException(status_code=404, detail=f"Service not found: {name}")
        return svc.status().to_dict()

    @router.get("/config")
    async def get_config(request: Request):
        """Return current config with secret values masked."""
        cm = request.app.state.config_manager
        return cm.get_config_masked()

    @router.get("/memory")
    async def get_memory(request: Request):
        """Detailed memory breakdown including per-service budgets."""
        registry = request.app.state.service_registry
        mem = psutil.virtual_memory()
        config = request.app.state.config_manager.config
        mem_config = config.get("memory", {})
        reserved = mem_config.get("reserved_gb", 7)

        services_mem = []
        total_expected = 0.0
        for svc_status in registry.all_status():
            expected = svc_status.get("expected_memory_gb", 0)
            total_expected += expected
            services_mem.append({
                "name": svc_status["name"],
                "state": svc_status["state"],
                "expected_gb": expected,
            })

        total_gb = round(mem.total / (1024 ** 3), 1)
        available_for_models = max(0, total_gb - reserved)

        return {
            "system": {
                "total_gb": total_gb,
                "used_gb": round(mem.used / (1024 ** 3), 1),
                "available_gb": round(mem.available / (1024 ** 3), 1),
                "percent": mem.percent,
            },
            "budget": {
                "reserved_gb": reserved,
                "available_for_models_gb": round(available_for_models, 1),
                "allocated_gb": round(total_expected, 1),
                "remaining_gb": round(available_for_models - total_expected, 1),
            },
            "services": services_mem,
        }

    return router
