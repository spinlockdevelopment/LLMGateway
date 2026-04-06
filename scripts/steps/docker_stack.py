"""
Docker Compose stack launch and health-check provisioning step.

Brings up the Docker Compose stack if it is not already running.
Supports optional observability stack (Grafana, Prometheus, Loki, Alloy).
"""

from __future__ import annotations

import json
import platform
import time
from pathlib import Path

from . import info, success, warn, cerror, dim, green, cyan, provision, run, log

_STABILIZE_WAIT = 30
_LITELLM_HEALTH_RETRIES = 6
_LITELLM_HEALTH_INTERVAL = 15


def _compose_cmd(
    repo_dir: Path,
    data_dir: Path,
    observability: bool,
    *args: str,
) -> list[str]:
    """Build docker compose command with appropriate files and env."""
    compose_file = repo_dir / "docker" / "docker-compose.yml"
    cmd = ["docker", "compose", "-f", str(compose_file)]
    if observability:
        obs_file = repo_dir / "docker" / "docker-compose.observability.yml"
        cmd.extend(["-f", str(obs_file)])
    env_file = data_dir / ".env"
    if env_file.exists():
        cmd.extend(["--env-file", str(env_file)])
    cmd.extend(args)
    return cmd


def _check_http(url: str, expect_2xx: bool = False) -> bool:
    """Return True if the endpoint is reachable."""
    if expect_2xx:
        result = run(
            ["curl", "-sf", "-o", "/dev/null", "-w", "%{http_code}", url],
            check=False, timeout=15,
        )
        return result.returncode == 0 and result.stdout.strip().startswith("2")
    else:
        result = run(["curl", "-sf", url], check=False, timeout=15)
        return result.returncode == 0


def _is_running(repo_dir: Path, data_dir: Path, observability: bool) -> bool:
    """Return True if at least one container is running."""
    result = run(
        _compose_cmd(repo_dir, data_dir, observability, "ps", "--format", "json"),
        check=False, timeout=30,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return False
    try:
        containers = [
            json.loads(line)
            for line in result.stdout.strip().splitlines()
            if line.strip()
        ]
        return any(
            c.get("State", c.get("state", "")).lower() == "running"
            for c in containers
        )
    except (json.JSONDecodeError, KeyError):
        return False


def _launch(repo_dir: Path, data_dir: Path, observability: bool) -> None:
    """Pull images, start services, wait for stabilization."""
    result = run(["docker", "info"], check=False, capture=True, timeout=15)
    if result.returncode != 0:
        raise RuntimeError("Docker daemon is not running — start Docker Desktop first")

    env_file = data_dir / ".env"
    if env_file.exists():
        try:
            content = env_file.read_text(errors="replace")
            if any(m in content for m in ("your-key-here", "change-me", "changeme")):
                warn(".env contains placeholder values — update via dashboard Secrets tab")
        except OSError:
            pass

    if platform.system() == "Darwin":
        info(
            "  On macOS you may see 'Terminal would like to access data from other apps' — "
            "click Allow once."
        )

    info("  Pulling latest Docker images (this may take a while)...")
    pull_result = run(
        _compose_cmd(repo_dir, data_dir, observability, "pull"),
        check=False, timeout=600,
    )
    if pull_result.returncode != 0:
        warn("docker compose pull reported errors — proceeding with cached images")

    info("  Starting services (docker compose up -d)...")
    run(
        _compose_cmd(repo_dir, data_dir, observability, "up", "-d", "--remove-orphans"),
        capture=False, timeout=300,
    )

    info(f"  Waiting {_STABILIZE_WAIT}s for services to stabilize...")
    time.sleep(_STABILIZE_WAIT)

    # LiteLLM often needs extra time for DB migrations
    litellm_url = "http://localhost:4000/health/liveliness"
    for attempt in range(1, _LITELLM_HEALTH_RETRIES + 1):
        if _check_http(litellm_url):
            success(f"LiteLLM proxy: {dim('ready')}")
            break
        info(
            f"  LiteLLM not yet ready (attempt {attempt}/{_LITELLM_HEALTH_RETRIES}), "
            f"waiting {_LITELLM_HEALTH_INTERVAL}s..."
        )
        time.sleep(_LITELLM_HEALTH_INTERVAL)
    else:
        warn("LiteLLM proxy did not become ready; check: docker compose logs litellm")

    ps_result = run(
        _compose_cmd(repo_dir, data_dir, observability, "ps", "--format", "json"),
        check=False, timeout=30,
    )
    _run_health_checks(ps_result, observability)


def _run_health_checks(ps_result, observability: bool) -> None:
    """Log pass/fail for each service health endpoint."""
    info("  Health checks:")

    if ps_result.returncode == 0 and ps_result.stdout.strip():
        try:
            for line in ps_result.stdout.strip().splitlines():
                if not line.strip():
                    continue
                c = json.loads(line)
                name = c.get("Name", c.get("name", "?"))
                state = c.get("State", c.get("state", "?"))
                health = c.get("Health", c.get("health", ""))
                label = state + (f" ({health})" if health else "")
                if state.lower() == "running":
                    info(f"    {green('+')} {name}: {label}")
                else:
                    cerror(f"  {name}: {label}")
        except (json.JSONDecodeError, KeyError) as e:
            warn(f"Could not parse container status: {e}")

    # HTTP endpoint checks
    checks = [("LiteLLM Proxy", "http://localhost:4000/health/liveliness", False)]
    if observability:
        checks.extend([
            ("Grafana", "http://localhost:3000/api/health", True),
            ("Prometheus", "http://localhost:9090/-/healthy", False),
        ])

    for svc_name, url, expect_2xx in checks:
        ok = _check_http(url, expect_2xx)
        if ok:
            info(f"    {green('+')} {svc_name}: healthy")
        else:
            warn(f"{svc_name}: not responding (may still be starting)")

    info("")
    info(f"  Endpoints:")
    info(f"    LiteLLM Proxy:  {cyan('http://localhost:4000')}")
    info(f"    LiteLLM UI:     {cyan('http://localhost:4000/ui')}")
    if observability:
        info(f"    Grafana:        {cyan('http://localhost:3000')}")
        info(f"    Prometheus:     {cyan('http://localhost:9090')}")


def setup(
    repo_dir: Path,
    data_dir: Path,
    observability: bool = False,
    dry_run: bool = False,
) -> bool:
    """Ensure Docker Compose stack is running."""
    compose_file = repo_dir / "docker" / "docker-compose.yml"
    if not compose_file.exists():
        cerror(f"docker-compose.yml not found: {compose_file}")
        return False

    label = "Docker Compose Stack"
    if observability:
        label += " + Observability"

    return provision(
        name=label,
        is_ready=lambda: _is_running(repo_dir, data_dir, observability),
        install=lambda: _launch(repo_dir, data_dir, observability),
        dry_run=dry_run,
    )
