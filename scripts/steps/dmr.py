"""
Docker Model Runner (DMR) provisioning step.

Enables Docker Desktop's built-in Model Runner feature and verifies
the REST API is reachable. Non-fatal if DMR does not respond immediately
(the service may need a few seconds after being enabled).
"""

from __future__ import annotations

import urllib.error
import urllib.request
from typing import Optional

from . import ProvisioningStep, log, run

_DMR_URL = "http://localhost:12434/engines/v1/models"


class DockerModelRunner(ProvisioningStep):
    """
    Ensures Docker Desktop Model Runner is enabled and responding.

    - install():  docker desktop enable model-runner --tcp 12434
    - is_installed(): always True (DMR ships with Docker Desktop)
    - _on_already_installed(): verifies the REST endpoint responds.
    """

    name = "Docker Model Runner"

    # ── Interface ─────────────────────────────────────────────────────────────

    def is_installed(self) -> bool:
        # DMR ships with Docker Desktop; we treat it as always "installed"
        # and use install() to enable/configure it.
        return self._is_responding()

    def current_version(self) -> Optional[str]:
        # No version introspection available; return a placeholder when running.
        if self._is_responding():
            return "enabled"
        return None

    def install(self) -> None:
        log.info("  Enabling Docker Model Runner (TCP port 12434)...")
        result = run(
            ["docker", "desktop", "enable", "model-runner", "--tcp", "12434"],
            check=False,
            timeout=60,
        )
        if result.returncode != 0:
            log.warning(
                f"  docker desktop enable model-runner exited {result.returncode} "
                "(non-fatal — DMR may already be enabled or Docker Desktop "
                "may need a restart)"
            )
        else:
            log.info("  Model Runner enabled")

        self._verify()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _is_responding(self) -> bool:
        """Return True if the DMR REST API answers at the expected URL."""
        try:
            with urllib.request.urlopen(_DMR_URL, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False

    def _verify(self) -> None:
        """Log whether DMR is responding; non-fatal if not."""
        if self._is_responding():
            log.info(f"  Model Runner API: responding ({_DMR_URL})")
        else:
            log.warning(
                "  Model Runner API not yet responding — this is non-fatal. "
                "Docker Desktop may need a moment to start the service. "
                f"Verify manually: curl {_DMR_URL}"
            )

    # ── Already-installed hook ────────────────────────────────────────────────

    def _on_already_installed(self) -> None:
        log.info(f"  Model Runner API: already responding ({_DMR_URL})")
