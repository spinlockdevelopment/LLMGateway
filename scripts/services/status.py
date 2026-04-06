"""
Async system status checks for the dashboard Status tab.

Replicates the key status logic from the ``gw`` CLI using async subprocess
calls so it can run inside the FastAPI event loop.
"""

from __future__ import annotations

import asyncio
import datetime
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
from data_dir import load_install_config
from services import run_cmd, http_ok


MANAGEMENT_PORT = 8080
MANAGEMENT_LABEL = "com.local.llm-gateway"
WHISPER_SERVER_DEFAULT_PORT = 8083

_DOCKER_ROWS = [
    ("llm-gateway", "litellm", "http://localhost:4000", "LiteLLM proxy (UI -> /ui)"),
    ("llm-postgres", "postgres", "", "PostgreSQL — spend tracking"),
]
_DOCKER_OBS_ROWS = [
    ("grafana", "grafana", "http://localhost:3000", "Grafana dashboards"),
    ("prometheus", "prometheus", "http://localhost:9090", "Prometheus metrics"),
    ("loki", "loki", "http://localhost:3100", "Loki log aggregation"),
    ("alloy", "alloy", "", "Grafana Alloy collector"),
]


# ── Low-level helpers ────────────────────────────────────────────────────────

async def _process_running(pattern: str) -> bool:
    rc, _, _ = await run_cmd(["pgrep", "-qf", pattern], timeout=5)
    return rc == 0


# ── Component state checks ──────────────────────────────────────────────────

async def docker_available() -> bool:
    rc, _, _ = await run_cmd(["docker", "info"], timeout=10)
    return rc == 0


async def docker_container_state(container: str) -> str:
    rc, stdout, _ = await run_cmd(
        ["docker", "inspect", "--format",
         "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}",
         container],
    )
    if rc != 0:
        return "absent"
    parts = stdout.strip().split("|", 1)
    status = parts[0]
    health = parts[1] if len(parts) > 1 else ""
    if status == "running":
        return "unhealthy" if health == "unhealthy" else "running"
    if status in ("exited", "dead"):
        return "stopped"
    if status == "restarting":
        return "starting"
    return status


async def management_state() -> str:
    if await http_ok(f"http://localhost:{MANAGEMENT_PORT}/"):
        return "running"
    if await _process_running("llmgateway.py"):
        return "starting"
    rc, stdout, _ = await run_cmd(["launchctl", "list"], timeout=10)
    if rc == 0 and MANAGEMENT_LABEL in stdout:
        return "stopped"
    plist = Path.home() / "Library" / "LaunchAgents" / f"{MANAGEMENT_LABEL}.plist"
    if plist.exists():
        return "stopped"
    return "absent"


async def whisper_server_state() -> str:
    if await http_ok(f"http://localhost:{WHISPER_SERVER_DEFAULT_PORT}/health"):
        return "running"
    if await _process_running("whisper-server"):
        return "starting"
    import shutil
    if shutil.which("whisper-server"):
        return "stopped"
    return "absent"


# ── Full status aggregator ──────────────────────────────────────────────────

async def get_full_status(repo_dir: Path, data_dir: Path) -> dict:
    """Return structured status matching the gw CLI output."""
    config = load_install_config(data_dir)
    obs = config.get("install_observability", False)

    enabled = {"management", "docker", "litellm", "postgres"}
    if obs:
        enabled.update({"grafana", "prometheus", "loki", "alloy"})
    if config.get("install_whisper", False):
        enabled.add("whisper-server")

    components = []

    # Bare-metal services
    if "management" in enabled:
        state = await management_state()
        components.append({
            "name": "management",
            "state": state,
            "endpoint": f"http://localhost:{MANAGEMENT_PORT}",
            "description": "Gateway web UI + REST API",
        })

    if "whisper-server" in enabled:
        state = await whisper_server_state()
        components.append({
            "name": "whisper-server",
            "state": state,
            "endpoint": f"http://localhost:{WHISPER_SERVER_DEFAULT_PORT}",
            "description": "Speech-to-text (whisper.cpp)",
        })

    # Docker containers (check concurrently)
    is_docker = await docker_available()
    if is_docker:
        rows = _DOCKER_ROWS + (_DOCKER_OBS_ROWS if obs else [])
        active_rows = [(c, d, e, desc) for c, d, e, desc in rows if d in enabled]
        if active_rows:
            states = await asyncio.gather(
                *(docker_container_state(c) for c, _, _, _ in active_rows)
            )
            for (_, display, endpoint, desc), state in zip(active_rows, states):
                components.append({
                    "name": display,
                    "state": state,
                    "endpoint": endpoint,
                    "description": desc,
                })

    # Service accounts
    user = os.environ.get("USER", "unknown")
    service_accounts = [
        {"role": "Host (local)", "user": user, "description": "management, whisper-server"},
        {"role": "PostgreSQL", "user": "litellm", "description": "LiteLLM DB (docker stack)"},
    ]
    if obs:
        grafana_user = "admin"
        env_file = data_dir / ".env"
        if env_file.exists():
            try:
                for line in env_file.read_text(errors="replace").splitlines():
                    if line.startswith("GF_SECURITY_ADMIN_USER="):
                        val = line.split("=", 1)[1].strip().strip("'\"")
                        if val:
                            grafana_user = val
            except Exception:
                pass
        service_accounts.append({
            "role": "Grafana admin",
            "user": grafana_user,
            "description": "docker stack (.env)",
        })

    # Key paths
    paths = {
        "config": [
            {"label": "config", "path": str(data_dir / "config" / "llmgateway.yaml"),
             "description": "gateway config + install choices"},
            {"label": "config", "path": "litellm-config.yaml",
             "description": "litellm: model routing"},
            {"label": "secrets", "path": str(data_dir / ".env"),
             "description": "API keys, passwords"},
        ],
        "logs": [
            {"label": "log", "path": str(data_dir / "logs" / "gateway.log"),
             "description": "management service (stdout + stderr)"},
            {"label": "log", "path": str(data_dir / "logs" / "gw.log"),
             "description": "gw script log"},
        ],
        "system": [
            {"label": "launchd", "path": str(
                Path.home() / "Library" / "LaunchAgents" / f"{MANAGEMENT_LABEL}.plist"),
             "description": "autostart agent"},
        ],
        "docker": [
            {"label": "docker", "path": str(repo_dir / "docker" / "docker-compose.yml"),
             "description": "core stack (LiteLLM + PostgreSQL)"},
        ],
    }
    if obs:
        paths["docker"].extend([
            {"label": "docker", "path": str(repo_dir / "docker" / "docker-compose.observability.yml"),
             "description": "observability stack"},
            {"label": "docker", "path": str(repo_dir / "docker" / "prometheus" / "prometheus.yml"),
             "description": "Prometheus scrape config"},
            {"label": "docker", "path": str(repo_dir / "docker" / "grafana" / "provisioning"),
             "description": "Grafana dashboards + data sources"},
            {"label": "docker", "path": str(repo_dir / "docker" / "alloy" / "alloy-config.alloy"),
             "description": "Grafana Alloy collector config"},
        ])

    # Check path existence
    for group in paths.values():
        for item in group:
            p = item["path"]
            expanded = str(Path(p).expanduser()) if p.startswith("~") else p
            if not os.path.isabs(expanded):
                expanded = str(repo_dir / expanded)
            item["exists"] = os.path.exists(expanded)

    return {
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "components": components,
        "service_accounts": service_accounts,
        "paths": paths,
        "docker_available": is_docker,
        "observability_enabled": obs,
    }
