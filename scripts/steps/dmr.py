"""
Docker Model Runner (DMR) provisioning step.

Enables Docker Desktop's built-in Model Runner feature and verifies
the REST API is reachable.
"""

from __future__ import annotations

import urllib.request

from . import info, success, warn, dim, provision, run

_DMR_URL = "http://localhost:12434/engines/v1/models"


def _is_responding() -> bool:
    """Return True if the DMR REST API answers."""
    try:
        with urllib.request.urlopen(_DMR_URL, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def _enable() -> None:
    """Enable DMR with TCP access."""
    info("  Enabling Docker Model Runner (TCP port 12434)...")
    result = run(
        ["docker", "desktop", "enable", "model-runner", "--tcp", "12434"],
        check=False,
        timeout=60,
    )
    if result.returncode != 0:
        warn(
            f"docker desktop enable model-runner exited {result.returncode} "
            "(non-fatal — may already be enabled)"
        )
    else:
        success(f"Model Runner: {dim('enabled')}")

    if _is_responding():
        success(f"Model Runner API: {dim(f'responding ({_DMR_URL})')}")
    else:
        warn(
            "Model Runner API not yet responding — Docker Desktop may need "
            f"a moment. Verify: curl {_DMR_URL}"
        )


def setup(dry_run: bool = False) -> bool:
    """Ensure Docker Model Runner is enabled and responding."""
    return provision(
        name="Docker Model Runner",
        is_ready=_is_responding,
        install=_enable,
        dry_run=dry_run,
    )
