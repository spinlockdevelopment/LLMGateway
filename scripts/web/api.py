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


# Substring signatures (matched against `process.name + ' ' + cmdline`, lowercased)
# used to classify memory usage into the System / Services / Models buckets.
# Docker Desktop on macOS hosts all stack containers (litellm, postgres, etc.)
# inside its VM, so the VM process — `com.docker.virtualization` — represents
# the entire managed stack on the host. Hence "docker" → services.
_MODEL_SIGS = (
    "llama-server", "llama.cpp", "llama_cpp",
    "ollama", "model-runner", "modelrunner",
    "vllm", "mlx-", "mlx_lm",
    "lmstudio", "lm-studio",
)
_SERVICE_SIGS = (
    "docker", "dockerd",                              # Docker Desktop / engine
    "com.apple.virtualization.virtualmachine",        # Docker Desktop's VM on macOS hosts our containers
    "litellm", "postgres", "grafana",                 # named services (if running outside Docker)
    "prometheus", "loki", "alloy",
    "llmgateway", "llm-gateway", "llmgateway.py",     # this gateway's own process
)


def _classify_process_bucket(name: str | None, cmdline: list[str] | None) -> str:
    """Return one of: 'models', 'services', 'system' (default)."""
    n = (name or "").lower()
    cl = " ".join(cmdline or []).lower() if cmdline else ""
    combined = n + " " + cl
    if any(sig in combined for sig in _MODEL_SIGS):
        return "models"
    if any(sig in combined for sig in _SERVICE_SIGS):
        return "services"
    return "system"


def _memory_breakdown_bytes() -> tuple[int, int]:
    """
    Walk processes once and return (services_rss, models_rss) in bytes.
    System bucket is computed by the caller as (mem.used - services - models)
    so the three add up to total used memory.
    """
    services = 0
    models = 0
    for p in psutil.process_iter(["name", "cmdline", "memory_info"]):
        try:
            info = p.info
            mi = info.get("memory_info")
            if mi is None:
                continue
            rss = mi.rss
            bucket = _classify_process_bucket(info.get("name"), info.get("cmdline"))
            if bucket == "models":
                models += rss
            elif bucket == "services":
                services += rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return services, models


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

        services_bytes, models_bytes = _memory_breakdown_bytes()
        # Cap and back out the system bucket so the three sum to mem.used.
        services_bytes = min(services_bytes, mem.used)
        models_bytes = min(models_bytes, mem.used - services_bytes)
        system_bytes = max(0, mem.used - services_bytes - models_bytes)
        gb = lambda b: round(b / (1024 ** 3), 1)  # noqa: E731

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
                "breakdown_gb": {
                    "system": gb(system_bytes),
                    "services": gb(services_bytes),
                    "models": gb(models_bytes),
                },
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

    @router.get("/processes/top")
    async def top_processes(request: Request):
        """Top N processes by resident memory (RSS). Default 10, max 50."""
        count_param = request.query_params.get("count", "10")
        try:
            count = max(1, min(int(count_param), 50))
        except ValueError:
            count = 10

        procs: list[dict[str, Any]] = []
        for p in psutil.process_iter(["pid", "name", "memory_info", "username", "cmdline"]):
            try:
                info = p.info
                mi = info.get("memory_info")
                if not mi:
                    continue
                procs.append({
                    "pid": info["pid"],
                    "name": info.get("name") or "?",
                    "user": info.get("username") or "",
                    "rss_mb": round(mi.rss / (1024 ** 2), 1),
                    "bucket": _classify_process_bucket(info.get("name"), info.get("cmdline")),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        procs.sort(key=lambda x: x["rss_mb"], reverse=True)
        return {"processes": procs[:count]}

    @router.get("/litellm/models")
    async def litellm_models(request: Request):
        """
        List unique model_names exposed by the LiteLLM proxy, parsed from
        litellm-config.yaml. Used by the dashboard to show endpoints clients
        can connect to.
        """
        repo_dir = getattr(request.app.state, "repo_dir", None)
        data_dir = getattr(request.app.state, "data_dir", None) or repo_dir

        candidates: list[Path] = []
        if data_dir is not None:
            candidates.append(data_dir / "litellm-config.yaml")
        if repo_dir is not None:
            candidates.append(repo_dir / "config" / "litellm-config.yaml")
        yaml_path = next((p for p in candidates if p.exists()), None)

        base_url = "http://localhost:4000"
        if yaml_path is None:
            return {"models": [], "base_url": base_url, "source": None}

        try:
            parsed = pyyaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        except pyyaml.YAMLError:
            return {"models": [], "base_url": base_url, "source": str(yaml_path)}

        groups: dict[str, list[str]] = {}
        order: list[str] = []
        for entry in parsed.get("model_list") or []:
            if not isinstance(entry, dict):
                continue
            name = entry.get("model_name")
            if not name:
                continue
            params = entry.get("litellm_params") or {}
            provider = params.get("model") or "?"
            if name not in groups:
                groups[name] = []
                order.append(name)
            groups[name].append(provider)

        alias_lookup: dict[str, list[str]] = {}
        router_settings = parsed.get("router_settings") or {}
        for alias, target in (router_settings.get("model_group_alias") or {}).items():
            alias_lookup.setdefault(target, []).append(alias)

        models = [
            {
                "name": name,
                "providers": groups[name],
                "aliases": alias_lookup.get(name, []),
            }
            for name in order
        ]
        return {"models": models, "base_url": base_url, "source": str(yaml_path)}

    @router.get("/litellm/routes")
    async def litellm_routes(request: Request):
        """
        Annotated route table parsed from litellm-config.yaml.

        Each row tells you: which pseudo-model the client requests, where the
        request actually goes (provider/backend), and which env var (and
        whether it's set in .env) authenticates the call.
        """
        repo_dir = getattr(request.app.state, "repo_dir", None)
        data_dir = getattr(request.app.state, "data_dir", None) or repo_dir

        candidates: list[Path] = []
        if data_dir is not None:
            candidates.append(data_dir / "litellm-config.yaml")
        if repo_dir is not None:
            candidates.append(repo_dir / "config" / "litellm-config.yaml")
        yaml_path = next((p for p in candidates if p.exists()), None)

        if yaml_path is None:
            return {"routes": [], "aliases": {}, "fallbacks": [], "env_keys_present": []}

        try:
            parsed = pyyaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        except pyyaml.YAMLError:
            return {"routes": [], "aliases": {}, "fallbacks": [], "env_keys_present": []}

        # Which env vars are actually set (in the .env file LiteLLM reads).
        env_keys_present: set[str] = set()
        if data_dir is not None:
            env_path = data_dir / ".env"
            if env_path.exists():
                for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, val = line.partition("=")
                    if val.strip():
                        env_keys_present.add(key.strip())

        def _classify(provider: str, api_base: str | None) -> str:
            p = (provider or "").lower()
            base = (api_base or "").lower()
            if "model-runner.docker.internal" in base:
                return "docker-model-runner"
            if p.startswith("openrouter/"):
                return "openrouter"
            if p.startswith("anthropic/"):
                return "anthropic"
            if p.startswith("gemini/") or p.startswith("vertex_ai/"):
                return "gemini"
            if p.startswith("xai/") or "x.ai" in base:
                return "xai"
            if p.startswith("azure/"):
                return "azure"
            if p.startswith("openai/"):
                if "localhost" in base or "host.docker.internal" in base or "127.0.0.1" in base:
                    return "local-llamacpp"
                return "openai"
            if p.startswith("deepseek/"):
                return "deepseek"
            return "other"

        def _env_key(api_key_field: Any) -> str | None:
            if isinstance(api_key_field, str) and api_key_field.startswith("os.environ/"):
                return api_key_field.split("/", 1)[1]
            return None

        routes: list[dict[str, Any]] = []
        for entry in parsed.get("model_list") or []:
            if not isinstance(entry, dict):
                continue
            name = entry.get("model_name")
            if not name:
                continue
            params = entry.get("litellm_params") or {}
            provider = params.get("model") or ""
            api_base = params.get("api_base")
            env_key = _env_key(params.get("api_key"))
            routes.append({
                "model_name": name,
                "provider": provider,
                "backend": _classify(provider, api_base),
                "api_base": api_base,
                "env_key": env_key,
                "env_key_set": (env_key in env_keys_present) if env_key else None,
                "order": params.get("order"),
                "rpm": params.get("rpm"),
                "tpm": params.get("tpm"),
            })

        # search_tools: web-search providers proxied by LiteLLM via the
        # websearch_interception callback. Shape mirrors model routes so the
        # dashboard can render them in the same table.
        search_tools: list[dict[str, Any]] = []
        for entry in parsed.get("search_tools") or []:
            if not isinstance(entry, dict):
                continue
            name = entry.get("search_tool_name")
            if not name:
                continue
            params = entry.get("litellm_params") or {}
            provider = params.get("search_provider") or ""
            env_key = _env_key(params.get("api_key"))
            search_tools.append({
                "search_tool_name": name,
                "search_provider": provider,
                "env_key": env_key,
                "env_key_set": (env_key in env_keys_present) if env_key else None,
            })

        router_settings = parsed.get("router_settings") or {}
        litellm_settings = parsed.get("litellm_settings") or {}

        # Pull the active web-search tool name (if any) so the dashboard can
        # flag the default. None → LiteLLM uses the first search_tools entry.
        active_search_tool = None
        for cb in litellm_settings.get("callbacks") or []:
            if isinstance(cb, dict) and "websearch_interception" in cb:
                wsi = cb["websearch_interception"] or {}
                active_search_tool = wsi.get("search_tool_name")
                break

        return {
            "routes": routes,
            "search_tools": search_tools,
            "active_search_tool": active_search_tool,
            "aliases": router_settings.get("model_group_alias") or {},
            "fallbacks": litellm_settings.get("fallbacks") or [],
            "context_window_fallbacks": litellm_settings.get("context_window_fallbacks") or [],
            "env_keys_present": sorted(env_keys_present),
            "source": str(yaml_path),
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
