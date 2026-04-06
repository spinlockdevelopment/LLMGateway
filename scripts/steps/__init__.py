"""
Shared utilities for LLM Gateway provisioning steps.

Each step is a module with functions rather than a class hierarchy.
The provision() helper provides consistent logging and error handling.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

log = logging.getLogger("llm-gateway-provision")

# Import console helpers for rich output — step modules re-export these
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
from console import (  # noqa: E402
    info, success, warn, error as cerror, heading, blank,
    dim, green, yellow, cyan,
)


# ── Subprocess helper ─────────────────────────────────────────────────────────

def run(
    cmd: list[str] | str,
    check: bool = True,
    capture: bool = True,
    shell: bool = False,
    timeout: int = 300,
) -> subprocess.CompletedProcess:
    """Run a subprocess command, log it, and return the result."""
    cmd_str = cmd if isinstance(cmd, str) else " ".join(str(c) for c in cmd)
    log.debug(f"  $ {cmd_str}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            check=check,
            shell=shell,
            timeout=timeout,
        )
        if result.stdout and result.stdout.strip():
            log.debug(f"  stdout: {result.stdout.strip()[:500]}")
        if result.stderr and result.stderr.strip():
            log.debug(f"  stderr: {result.stderr.strip()[:500]}")
        return result
    except subprocess.CalledProcessError as e:
        cerror(f"Command failed (exit {e.returncode}): {cmd_str}")
        if e.stdout:
            log.debug(f"  stdout: {e.stdout.strip()[:500]}")
        if e.stderr:
            log.debug(f"  stderr: {e.stderr.strip()[:500]}")
        raise
    except subprocess.TimeoutExpired:
        cerror(f"Command timed out after {timeout}s: {cmd_str}")
        raise


def command_exists(cmd: str) -> bool:
    """Return True if *cmd* is found on PATH."""
    return shutil.which(cmd) is not None


# ── Provisioning helper ──────────────────────────────────────────────────────

def provision(
    name: str,
    is_ready: Callable[[], bool],
    install: Callable[[], None],
    dry_run: bool = False,
) -> bool:
    """
    Idempotent provisioning: check if ready, install if not.

    Returns True on success, False on failure.
    """
    heading(name)

    try:
        if dry_run:
            ready = is_ready()
            if ready:
                success(f"{name}: {green('ready')}")
            else:
                info(f"  {yellow('!')} {name}: {yellow('not ready')}")
            return True

        if is_ready():
            success(f"{name}: {dim('already ready')}")
        else:
            install()

        return True

    except Exception as e:
        cerror(f"{name}: {e}")
        log.debug("  Stack trace:", exc_info=True)
        return False
