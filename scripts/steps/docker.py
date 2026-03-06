"""
Docker Desktop + Docker Compose provisioning step.

Installs Docker Desktop via Homebrew cask, waits for the daemon to respond,
and verifies Docker Compose is available. If Docker is already installed but
not running, attempts to open Docker Desktop and waits for the daemon.
"""

from __future__ import annotations

import time
from typing import Optional

from . import ProvisioningStep, command_exists, log, run

_WAIT_SECONDS = 150
_POLL_INTERVAL = 5


class DockerDesktop(ProvisioningStep):
    """
    Ensures Docker Desktop (including Docker Compose) is installed and running.

    - install():  brew install --cask docker  + waits for daemon
    - upgrade():  brew upgrade --cask docker
    - _on_already_installed(): starts daemon if not running, checks Compose.
    """

    name = "Docker Desktop"

    # ── Interface ─────────────────────────────────────────────────────────────

    def is_installed(self) -> bool:
        return command_exists("docker")

    def current_version(self) -> Optional[str]:
        if not self.is_installed():
            return None
        result = run(["docker", "--version"], check=False)
        return result.stdout.strip() if result.returncode == 0 else None

    def install(self) -> None:
        # Check if the cask is already present (app installed but docker CLI missing?)
        cask_check = run(["brew", "list", "--cask", "docker"], check=False, timeout=20)
        if cask_check.returncode == 0:
            log.info("  Docker cask already installed — attempting to start daemon...")
        else:
            log.info("  Installing Docker Desktop via Homebrew cask...")
            run(["brew", "install", "--cask", "docker"], timeout=600)
            log.info("  Docker Desktop cask installed")

        # Open Docker Desktop so it can finish first-run setup
        run(["open", "-a", "Docker"], check=False)
        self._wait_for_daemon()

    def upgrade(self) -> None:
        log.info("  Upgrading Docker Desktop via Homebrew cask...")
        run(["brew", "upgrade", "--cask", "docker"], check=False, timeout=600)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def is_daemon_running(self) -> bool:
        """Return True if the Docker daemon responds to 'docker info'."""
        result = run(["docker", "info"], check=False, capture=True, timeout=10)
        return result.returncode == 0

    def _wait_for_daemon(self) -> None:
        """Poll until Docker daemon is responsive or timeout elapses."""
        log.info(f"  Waiting up to {_WAIT_SECONDS}s for Docker daemon...")
        log.info("  (Accept the Docker Desktop license dialog if prompted)")
        for elapsed in range(0, _WAIT_SECONDS, _POLL_INTERVAL):
            if self.is_daemon_running():
                log.info(f"  Docker daemon: ready (after {elapsed}s)")
                return
            time.sleep(_POLL_INTERVAL)
            if elapsed > 0 and elapsed % 30 == 0:
                log.info(f"  Still waiting for Docker ({elapsed}s elapsed)...")
        log.warning(
            f"  Docker daemon did not respond within {_WAIT_SECONDS}s. "
            "Start Docker Desktop manually and re-run this script."
        )

    def _check_compose(self) -> None:
        """Log Docker Compose availability and version."""
        result = run(["docker", "compose", "version"], check=False, timeout=15)
        if result.returncode == 0:
            log.info(f"  Docker Compose: {result.stdout.strip()}")
        else:
            log.warning(
                "  Docker Compose not found — it should ship with Docker Desktop. "
                "Try restarting Docker Desktop, or: brew install docker-compose"
            )

    # ── Already-installed hook ────────────────────────────────────────────────

    def _on_already_installed(self) -> None:
        if not self.is_daemon_running():
            log.info("  Docker daemon not running — attempting to open Docker Desktop...")
            run(["open", "-a", "Docker"], check=False)
            self._wait_for_daemon()
        else:
            log.info("  Docker daemon: running")

        self._check_compose()
