"""
Docker Compose stack launch and health-check provisioning step.

Brings up the Docker Compose stack if it is not already running. If the
stack is running, performs health checks only — no restart. Sanity checks
hit each service's health/readiness endpoint and log pass/fail per service.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from . import ProvisioningStep, log, run

# Services checked after stack launch. Tuple: (label, url, expect_http_2xx)
_HEALTH_CHECKS = [
    ("LiteLLM Proxy",  "http://localhost:4000/health/liveliness",       False),
    ("Grafana",        "http://localhost:3000/api/health",               True),
    ("Prometheus",     "http://localhost:9090/-/healthy",                False),
    ("Ollama (host)",  "http://localhost:11434/api/tags",                False),  # optional
]

_STABILIZE_WAIT = 30  # seconds to wait after `docker compose up -d`


class DockerStack(ProvisioningStep):
    """
    Manages the Docker Compose stack lifecycle.

    - is_installed():    True if docker-compose.yml exists.
    - current_version(): summary of running/total containers.
    - install():         launches the stack (pull + up -d + health checks).
    - provision():       fully overridden — launches if not running, else checks.
    """

    name = "Docker Compose Stack"

    def __init__(self, repo_dir: Path) -> None:
        self.repo_dir = repo_dir
        self._compose_file = repo_dir / "docker" / "docker-compose.yml"

    # ── Interface ─────────────────────────────────────────────────────────────

    def is_installed(self) -> bool:
        """True if the compose file is present (a necessary precondition)."""
        return self._compose_file.exists()

    def current_version(self) -> Optional[str]:
        """Return a human-readable count of running containers."""
        result = run(
            ["docker", "compose", "-f", str(self._compose_file), "ps", "--format", "json"],
            check=False,
            timeout=30,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        try:
            containers = [
                json.loads(line)
                for line in result.stdout.strip().splitlines()
                if line.strip()
            ]
            running = sum(
                1
                for c in containers
                if c.get("State", c.get("state", "")).lower() == "running"
            )
            return f"{running}/{len(containers)} containers running"
        except (json.JSONDecodeError, KeyError):
            return None

    def install(self) -> None:
        """Launch the stack (pull images, docker compose up -d, health check)."""
        self._launch()

    # ── Orchestration override ────────────────────────────────────────────────

    def provision(self, dry_run: bool = False) -> bool:
        """
        Override: launch the stack if not running; health check if already up.
        In dry_run mode, only reports status.
        """
        log.info(self._section_header())

        if not self._compose_file.exists():
            log.error(f"  docker-compose.yml not found: {self._compose_file}")
            return False

        try:
            if dry_run:
                status = self.current_version()
                log.info(f"  Status: {status or 'not running'}")
                self._run_health_checks()
                return True

            if self._is_running():
                log.info(f"  Stack already running: {self.current_version()}")
                self._run_health_checks()
            else:
                log.info("  Stack not running — launching...")
                self._launch()

            return True

        except Exception as e:
            log.error(f"  Stack provisioning FAILED: {e}")
            log.debug("  Stack trace:", exc_info=True)
            return False

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _is_running(self) -> bool:
        """Return True if at least one container is in the 'running' state."""
        result = run(
            ["docker", "compose", "-f", str(self._compose_file), "ps", "--format", "json"],
            check=False,
            timeout=30,
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

    def _launch(self) -> None:
        """Pull images, start services, wait for stabilization."""
        # Verify Docker daemon is responsive
        result = run(["docker", "info"], check=False, capture=True, timeout=15)
        if result.returncode != 0:
            raise RuntimeError(
                "Docker daemon is not running — start Docker Desktop first"
            )

        # Validate .env has been configured
        env_file = self.repo_dir / ".env"
        if env_file.exists():
            try:
                content = env_file.read_text(errors="replace")
                if any(m in content for m in ("your-key-here", "change-me", "changeme")):
                    raise RuntimeError(
                        ".env still contains placeholder API keys — "
                        "configure LITELLM_MASTER_KEY and any provider keys (e.g. OPENROUTER_API_KEY) as needed"
                    )
            except OSError as e:
                log.warning(f"  Could not read .env for validation: {e}")

        # Pull latest images
        log.info("  Pulling latest Docker images (this may take a while)...")
        run(
            ["docker", "compose", "-f", str(self._compose_file), "pull"],
            check=False,
            timeout=600,
        )

        # Bring up the stack
        log.info("  Starting services (docker compose up -d)...")
        run(
            [
                "docker", "compose",
                "-f", str(self._compose_file),
                "up", "-d", "--remove-orphans",
            ],
            timeout=300,
        )

        log.info(f"  Waiting {_STABILIZE_WAIT}s for services to stabilize...")
        time.sleep(_STABILIZE_WAIT)

        self._run_health_checks()

    def _check_http(self, url: str, expect_2xx: bool = False) -> bool:
        """
        Return True if the endpoint is reachable.
        If expect_2xx=True, also verifies the HTTP status starts with '2'.
        """
        if expect_2xx:
            result = run(
                ["curl", "-sf", "-o", "/dev/null", "-w", "%{http_code}", url],
                check=False,
                timeout=15,
            )
            return result.returncode == 0 and result.stdout.strip().startswith("2")
        else:
            result = run(["curl", "-sf", url], check=False, timeout=15)
            return result.returncode == 0

    def _run_health_checks(self) -> None:
        """Log pass/fail for each service health endpoint."""
        log.info("  Health checks:")
        all_critical_ok = True

        # Container-level status from docker compose ps
        result = run(
            ["docker", "compose", "-f", str(self._compose_file), "ps", "--format", "json"],
            check=False,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            try:
                for line in result.stdout.strip().splitlines():
                    if not line.strip():
                        continue
                    c = json.loads(line)
                    name = c.get("Name", c.get("name", "?"))
                    state = c.get("State", c.get("state", "?"))
                    health = c.get("Health", c.get("health", ""))
                    label = state + (f" ({health})" if health else "")
                    if state.lower() == "running":
                        log.info(f"    ✓ {name}: {label}")
                    else:
                        log.error(f"    ✗ {name}: {label}")
                        all_critical_ok = False
            except (json.JSONDecodeError, KeyError) as e:
                log.warning(f"    Could not parse container status: {e}")

        # HTTP endpoint checks
        for svc_name, url, expect_2xx in _HEALTH_CHECKS:
            ok = self._check_http(url, expect_2xx)
            is_optional = "Ollama" in svc_name
            if ok:
                log.info(f"    ✓ {svc_name}: healthy")
            elif is_optional:
                log.warning(f"    ⚠ {svc_name}: not responding (optional — run: ollama serve)")
            else:
                log.warning(f"    ⚠ {svc_name}: not responding (may still be starting)")

        # Summary
        if all_critical_ok:
            log.info("")
            log.info("  Stack is healthy:")
            log.info("    LiteLLM Proxy:  http://localhost:4000")
            log.info("    LiteLLM UI:     http://localhost:4000/ui")
            log.info("    Grafana:        http://localhost:3000")
            log.info("    Prometheus:     http://localhost:9090")
        else:
            log.error("")
            log.error("  One or more containers are not running!")
            log.error(
                f"  Check logs: docker compose -f {self._compose_file} logs"
            )
