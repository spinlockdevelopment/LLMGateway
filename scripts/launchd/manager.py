"""
macOS launchd integration for the LLM Gateway service.

Generates a launchd plist, installs/uninstalls it to ~/Library/LaunchAgents,
and provides load/unload commands. Runs as a user agent (not a system daemon)
so it starts on user login without requiring root.
"""

from __future__ import annotations

import logging
import plistlib
import subprocess
import sys
from pathlib import Path
from typing import Optional

log = logging.getLogger("llm-gateway")

_LABEL = "com.local.llm-gateway"
_PLIST_DIR = Path.home() / "Library" / "LaunchAgents"


def _plist_path() -> Path:
    return _PLIST_DIR / f"{_LABEL}.plist"


def generate_plist(
    python_bin: str,
    script_path: str,
    config_dir: str,
    port: int = 8080,
    log_dir: Optional[str] = None,
) -> dict:
    """
    Build the plist dict for the LLM Gateway launch agent.

    Args:
        python_bin:  Absolute path to the Python interpreter.
        script_path: Absolute path to scripts/llmgateway.py.
        config_dir:  Absolute path to the config/ directory.
        port:        Gateway web UI port.
        log_dir:     Directory for stdout/stderr logs (default: ~/Library/Logs).
    """
    if log_dir is None:
        log_dir = str(Path.home() / "Library" / "Logs" / "llm-gateway")

    Path(log_dir).mkdir(parents=True, exist_ok=True)

    return {
        "Label": _LABEL,
        "ProgramArguments": [
            python_bin,
            script_path,
        ],
        "WorkingDirectory": str(Path(script_path).parent.parent),
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 10,
        "StandardOutPath": f"{log_dir}/gateway-stdout.log",
        "StandardErrorPath": f"{log_dir}/gateway-stderr.log",
        "EnvironmentVariables": {
            "PYTHONUNBUFFERED": "1",
            "PATH": "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin",
        },
    }


def install(
    repo_dir: Path,
    port: int = 8080,
) -> bool:
    """
    Generate the plist and install it to ~/Library/LaunchAgents.
    Returns True on success.
    """
    python_bin = sys.executable
    script_path = str(repo_dir / "scripts" / "llmgateway.py")
    config_dir = str(repo_dir / "config")

    # Unload existing if present (idempotent)
    uninstall(quiet=True)

    plist_data = generate_plist(
        python_bin=python_bin,
        script_path=script_path,
        config_dir=config_dir,
        port=port,
    )

    plist_file = _plist_path()
    _PLIST_DIR.mkdir(parents=True, exist_ok=True)

    try:
        with open(plist_file, "wb") as f:
            plistlib.dump(plist_data, f)
        log.info(f"  Plist written: {plist_file}")
    except OSError as e:
        log.error(f"  Failed to write plist: {e}")
        return False

    # Load the agent
    result = subprocess.run(
        ["launchctl", "load", str(plist_file)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        err = result.stderr.strip() or result.stdout.strip()
        log.error(f"  launchctl load failed: {err}")
        return False

    log.info(f"  Launch agent installed and loaded: {_LABEL}")
    log.info(f"  The gateway will start automatically on login")
    return True


def uninstall(quiet: bool = False) -> bool:
    """
    Unload and remove the launch agent plist.
    Returns True if uninstalled (or wasn't installed).
    """
    plist_file = _plist_path()

    if not plist_file.exists():
        if not quiet:
            log.info("  Launch agent not installed — nothing to remove")
        return True

    # Unload
    result = subprocess.run(
        ["launchctl", "unload", str(plist_file)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 and not quiet:
        err = result.stderr.strip() or result.stdout.strip()
        log.warning(f"  launchctl unload: {err}")

    # Remove plist file
    try:
        plist_file.unlink()
        if not quiet:
            log.info(f"  Launch agent removed: {_LABEL}")
    except OSError as e:
        if not quiet:
            log.error(f"  Failed to remove plist: {e}")
        return False

    return True


def is_installed() -> bool:
    """Return True if the launch agent plist exists."""
    return _plist_path().exists()


def is_loaded() -> bool:
    """Return True if the launch agent is currently loaded in launchctl."""
    result = subprocess.run(
        ["launchctl", "list"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return _LABEL in result.stdout


def status() -> dict:
    """Return launchd agent status."""
    installed = is_installed()
    loaded = is_loaded() if installed else False
    return {
        "label": _LABEL,
        "installed": installed,
        "loaded": loaded,
        "plist_path": str(_plist_path()),
    }
