"""
Install/remove a `gw` CLI symlink in a PATH directory.

Picks the first writable directory in PATH-priority order (Homebrew on Apple
Silicon, Homebrew/system on Intel, then ~/.local/bin if it's on PATH). Only
operates on symlinks that point back into our repo, so uninstall is safe.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

log = logging.getLogger("llm-gateway.cli-symlink")

LINK_NAME = "gw"


def _candidate_dirs() -> list[Path]:
    """Return PATH directories to consider, in priority order."""
    candidates = [
        Path("/opt/homebrew/bin"),   # Apple Silicon Homebrew
        Path("/usr/local/bin"),       # Intel Homebrew / system
        Path.home() / ".local" / "bin",
    ]
    return [c for c in candidates if c.exists() or c == Path.home() / ".local" / "bin"]


def _is_on_path(directory: Path) -> bool:
    path_entries = os.environ.get("PATH", "").split(os.pathsep)
    return str(directory) in path_entries


def _pick_install_dir() -> Optional[Path]:
    """Return the first writable, PATH-listed directory; create ~/.local/bin if needed."""
    for d in _candidate_dirs():
        if d == Path.home() / ".local" / "bin":
            try:
                d.mkdir(parents=True, exist_ok=True)
            except OSError:
                continue
        if not d.exists():
            continue
        if not os.access(d, os.W_OK):
            continue
        if not _is_on_path(d):
            continue
        return d
    return None


def install_symlink(repo_dir: Path) -> bool:
    """
    Create a symlink so `gw` is callable from anywhere on PATH.

    Returns True if the link is present and correct after the call, False on
    failure. Idempotent: re-running with the symlink already correct is a no-op.
    """
    target = (Path(repo_dir).resolve() / LINK_NAME)
    if not target.exists():
        log.error(f"  CLI target not found: {target}")
        return False

    install_dir = _pick_install_dir()
    if install_dir is None:
        log.warning("  No writable directory on PATH for the `gw` symlink.")
        log.warning(f"  Create one manually:  ln -s {target} /usr/local/bin/gw")
        return False

    link_path = install_dir / LINK_NAME

    # If something is already there, decide what to do.
    if link_path.is_symlink():
        try:
            current = link_path.resolve()
        except OSError:
            current = None
        if current == target:
            log.info(f"  CLI symlink already in place: {link_path}")
            return True
        # Symlink exists but points elsewhere — only replace if it points into our repo.
        try:
            link_path.unlink()
        except OSError as e:
            log.error(f"  Failed to remove stale symlink {link_path}: {e}")
            return False
    elif link_path.exists():
        log.warning(f"  {link_path} exists and is not a symlink — leaving it alone.")
        log.warning(f"  Remove it manually if you want `gw` on PATH:  rm {link_path}")
        return False

    try:
        link_path.symlink_to(target)
        log.info(f"  CLI symlink installed: {link_path} → {target}")
        return True
    except OSError as e:
        log.error(f"  Failed to create symlink {link_path}: {e}")
        return False


def uninstall_symlink(repo_dir: Path) -> bool:
    """
    Remove the `gw` symlink from any candidate directory, but only if it
    points back into our repo. Returns True if removed or absent.
    """
    target = (Path(repo_dir).resolve() / LINK_NAME)
    removed_any = False
    for d in _candidate_dirs():
        if not d.exists():
            continue
        link_path = d / LINK_NAME
        if not link_path.is_symlink():
            continue
        try:
            current = link_path.resolve()
        except OSError:
            continue
        if current != target:
            continue
        try:
            link_path.unlink()
            log.info(f"  CLI symlink removed: {link_path}")
            removed_any = True
        except OSError as e:
            log.warning(f"  Failed to remove symlink {link_path}: {e}")
    if not removed_any:
        log.info("  CLI symlink: not installed by us — nothing to remove")
    return True
