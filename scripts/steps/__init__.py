"""
Shared utilities for LLM Gateway provisioning steps.

Each step is a module with functions rather than a class hierarchy.
The provision() helper provides consistent logging and error handling.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from typing import Callable

log = logging.getLogger("llm-gateway-provision")

_HEADER_TOTAL_WIDTH = 50


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
        log.error(f"  Command failed (exit {e.returncode}): {cmd_str}")
        if e.stdout:
            log.error(f"  stdout: {e.stdout.strip()[:500]}")
        if e.stderr:
            log.error(f"  stderr: {e.stderr.strip()[:500]}")
        raise
    except subprocess.TimeoutExpired:
        log.error(f"  Command timed out after {timeout}s: {cmd_str}")
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
    prefix = f"── {name} "
    header = prefix + "─" * max(0, _HEADER_TOTAL_WIDTH - len(prefix))
    log.info(header)

    try:
        if dry_run:
            status = "ready" if is_ready() else "NOT READY"
            log.info(f"  Status: {status}")
            return True

        if is_ready():
            log.info(f"  Already ready")
        else:
            log.info(f"  Setting up...")
            install()

        return True

    except Exception as e:
        log.error(f"  FAILED: {e}")
        log.debug("  Stack trace:", exc_info=True)
        return False
