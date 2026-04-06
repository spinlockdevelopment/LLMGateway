"""
Docker Desktop verification step.

Checks that Docker Desktop is installed and the daemon is running.
If installed but not running, attempts to open Docker Desktop and waits.
"""

from __future__ import annotations

import time

from . import command_exists, info, success, warn, dim, provision, run

_WAIT_SECONDS = 150
_POLL_INTERVAL = 5


def is_daemon_running() -> bool:
    """Return True if the Docker daemon responds to 'docker info'."""
    result = run(["docker", "info"], check=False, capture=True, timeout=10)
    return result.returncode == 0


def _ensure_running() -> None:
    """Start Docker Desktop and wait for the daemon."""
    if not command_exists("docker"):
        raise RuntimeError(
            "Docker not found. Install Docker Desktop: https://docker.com/products/docker-desktop/"
        )

    if is_daemon_running():
        success(f"Docker daemon: {dim('running')}")
        return

    info("  Docker daemon not running — opening Docker Desktop...")
    run(["open", "-a", "Docker"], check=False)

    info(f"  Waiting up to {_WAIT_SECONDS}s for Docker daemon...")
    for elapsed in range(0, _WAIT_SECONDS, _POLL_INTERVAL):
        if is_daemon_running():
            success(f"Docker daemon: ready {dim(f'(after {elapsed}s)')}")
            return
        time.sleep(_POLL_INTERVAL)
        if elapsed > 0 and elapsed % 30 == 0:
            info(f"  Still waiting for Docker ({elapsed}s elapsed)...")

    warn(
        f"Docker daemon did not respond within {_WAIT_SECONDS}s. "
        "Start Docker Desktop manually and re-run."
    )


def setup(dry_run: bool = False) -> bool:
    """Ensure Docker Desktop is installed and daemon is running."""
    return provision(
        name="Docker Desktop",
        is_ready=lambda: command_exists("docker") and is_daemon_running(),
        install=_ensure_running,
        dry_run=dry_run,
    )
