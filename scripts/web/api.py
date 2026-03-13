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

import asyncio
import json
import platform
import sys
import time
from pathlib import Path
from typing import Any

import psutil
import yaml as pyyaml
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

    @router.get("/docker/containers")
    async def list_docker_containers(request: Request):
        """
        List all Docker containers with optional metadata from the gateway's
        docker-compose stack (config paths, data mounts, and exposed ports).
        """

        async def _docker_ps() -> list[dict[str, Any]]:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "docker",
                    "ps",
                    "-a",
                    "--format",
                    "{{json .}}",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            except FileNotFoundError:
                raise HTTPException(
                    status_code=503,
                    detail="docker CLI not found — install Docker Desktop first",
                )

            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                msg = stderr.decode(errors="replace").strip() or "docker ps failed"
                raise HTTPException(status_code=503, detail=msg)

            containers: list[dict[str, Any]] = []
            for raw in stdout.splitlines():
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    info = json.loads(raw.decode("utf-8"))
                except Exception:
                    continue
                containers.append(
                    {
                        "id": info.get("ID"),
                        "name": info.get("Names"),
                        "image": info.get("Image"),
                        "status": info.get("Status"),
                        "state": info.get("State"),
                        "ports": info.get("Ports"),
                        "created": info.get("RunningFor"),
                    }
                )
            return containers

        def _load_compose_metadata() -> dict[str, dict[str, Any]]:
            repo_dir = Path(__file__).resolve().parents[2]
            compose_path = repo_dir / "docker" / "docker-compose.yml"
            if not compose_path.exists():
                return {}

            try:
                doc = pyyaml.safe_load(compose_path.read_text(encoding="utf-8"))
            except Exception:
                return {}

            services = doc.get("services") or {}
            meta_by_container: dict[str, dict[str, Any]] = {}

            for svc_name, svc_cfg in services.items():
                container_name = svc_cfg.get("container_name") or svc_name
                ports_cfg = svc_cfg.get("ports") or []
                volumes_cfg = svc_cfg.get("volumes") or []

                config_paths: list[str] = []
                data_mounts: list[str] = []

                def _classify_volume(host: str, container_path: str) -> None:
                    # Normalize relative host paths against repo/docker dir.
                    if host.startswith("."):
                        host_path = compose_path.parent / host
                        host_str = str(host_path.resolve())
                    else:
                        host_str = host

                    entry = f"{host_str}:{container_path}"

                    lowered = host_str.lower()
                    if any(
                        token in lowered
                        for token in (
                            "config",
                            ".yaml",
                            ".yml",
                            ".alloy",
                            ".conf",
                        )
                    ):
                        config_paths.append(entry)
                    elif "/var/run/docker.sock" not in host_str:
                        data_mounts.append(entry)

                for vol in volumes_cfg:
                    if isinstance(vol, str):
                        if ":" in vol:
                            host, container_path = vol.split(":", 1)
                            _classify_volume(host, container_path)
                    elif isinstance(vol, dict):
                        host = str(vol.get("source") or vol.get("src") or "")
                        container_path = str(vol.get("target") or vol.get("dst") or "")
                        if host and container_path:
                            _classify_volume(host, container_path)

                meta_by_container[container_name] = {
                    "service": svc_name,
                    "compose_service": svc_name,
                    "config_paths": config_paths,
                    "data_mounts": data_mounts,
                    "declared_ports": ports_cfg,
                }

            return meta_by_container

        containers = await _docker_ps()
        compose_meta = _load_compose_metadata()

        for c in containers:
            meta = compose_meta.get(c.get("name") or "")
            if meta:
                c.update(meta)

        return {"containers": containers}

    return router
