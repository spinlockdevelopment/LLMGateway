#!/usr/bin/env python3
"""
Interactive SSH remote access setup helper for LLM Gateway.

This script is responsible for configuring SSH access to this machine:
  - Reports current Remote Login (sshd) status
  - Optionally enables Remote Login via sudo
  - Ensures a local SSH keypair exists (~/.ssh/id_ed25519)
  - Optionally adds an authorized public key from another machine

It is safe to run multiple times; all operations are idempotent. Skipping the
optional public key step does not cause the script to fail.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent.resolve()
_REPO_DIR = _SCRIPT_DIR.parent.resolve()
sys.path.insert(0, str(_SCRIPT_DIR))

from console import (  # type: ignore[import]
    info,
    success,
    warn,
    error,
    dim,
    green,
    yellow,
    heading,
    banner,
    blank,
    prompt_yes_no,
)
from steps.ssh_setup import (  # type: ignore[import]
    check_remote_login_status,
    enable_remote_login,
    ensure_local_ssh_key,
    validate_ssh_public_key,
    append_authorized_key,
)


def _report_status() -> None:
    """Print current Remote Login status."""
    status = check_remote_login_status()
    if status == "on":
        info(f"  Remote Login (SSH): {green('enabled')}")
    elif status == "off":
        info(f"  Remote Login (SSH): {yellow('disabled')}")
    else:
        info(f"  Remote Login (SSH): {dim('status unknown')}")


def _maybe_enable_remote_login() -> None:
    """Optionally enable Remote Login via sudo; never raises on failure."""
    status = check_remote_login_status()
    if status == "on":
        info(f"  Remote Login already enabled — no action needed")
        return

    if not prompt_yes_no("  Enable Remote Login (SSH)? (requires sudo)", default=False):
        info(f"  {dim('Leaving Remote Login unchanged.')}")
        return

    info("  Enabling Remote Login (SSH)...")
    if enable_remote_login():
        success("  Remote Login enabled.")
    else:
        error("  Failed to enable Remote Login.")
        error("  Try manually: sudo systemsetup -setremotelogin on")


def _ensure_local_keypair() -> None:
    """Ensure a local SSH keypair exists and report its location."""
    key_path = ensure_local_ssh_key()
    if key_path is not None:
        success(f"  Local SSH keypair ensured at: {key_path}")
    else:
        warn("  Could not create local SSH keypair (id_ed25519).")


def _maybe_add_authorized_key() -> None:
    """
    Optionally add an authorized public key from another machine.

    This step is optional and never causes the script to fail. Invalid keys
    are reported and skipped.
    """
    blank()
    info("  To allow SSH access from another machine, paste its public key.")
    info(f"  {dim('(On the remote machine: cat ~/.ssh/id_ed25519.pub)')}")
    try:
        raw = input("  Public key (or Enter to skip): ").strip()
    except (EOFError, KeyboardInterrupt):
        raw = ""

    if not raw:
        info(f"  {dim('No public key provided — skipping.')}")
        return

    if not validate_ssh_public_key(raw):
        warn("  That does not look like a valid SSH public key — skipping.")
        return

    if append_authorized_key(raw):
        parts = raw.split()
        comment = parts[2] if len(parts) >= 3 else parts[0][:20] + "..."
        success(f"  Authorized key added: {comment}")
    else:
        error("  Failed to add authorized key (authorized_keys update failed).")


def main() -> int:
    banner("SSH Remote Access Setup")
    blank()
    heading("Status")
    _report_status()
    blank()

    heading("Remote Login")
    _maybe_enable_remote_login()
    blank()

    heading("Local SSH Keypair")
    _ensure_local_keypair()
    blank()

    heading("Authorized Keys")
    _maybe_add_authorized_key()
    blank()

    success("SSH remote access setup helper finished.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

