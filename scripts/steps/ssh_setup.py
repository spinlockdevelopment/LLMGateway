"""
SSH remote access setup step.

Two-step flow (both optional, driven by SetupConfig):
  1. Enable Remote Login (macOS sshd) via: sudo systemsetup -setremotelogin on
  2. Add an authorized public key to ~/.ssh/authorized_keys

This replaces the old ssh_config.py which was report-only.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from . import ProvisioningStep, log


# SSH public key formats we recognize
_SSH_KEY_PREFIXES = (
    "ssh-rsa",
    "ssh-ed25519",
    "ssh-dss",
    "ecdsa-sha2-nistp256",
    "ecdsa-sha2-nistp384",
    "ecdsa-sha2-nistp521",
    "sk-ssh-ed25519",
    "sk-ecdsa-sha2-nistp256",
)


def validate_ssh_public_key(key: str) -> bool:
    """Return True if the string looks like a valid SSH public key."""
    key = key.strip()
    if not key:
        return False
    return any(key.startswith(prefix) for prefix in _SSH_KEY_PREFIXES)


def check_remote_login_status() -> str:
    """
    Check macOS Remote Login (sshd) status.
    Returns: "on", "off", or "unknown".
    """
    # Try passwordless sudo first (common in dev setups)
    try:
        result = subprocess.run(
            ["sudo", "-n", "systemsetup", "-getremotelogin"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            output = result.stdout.strip().lower()
            return "on" if "on" in output else "off"
    except Exception:
        pass

    # Fallback: check launchctl (no sudo required)
    try:
        result = subprocess.run(
            ["launchctl", "list", "com.openssh.sshd"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return "on"
    except Exception:
        pass

    return "unknown"


def enable_remote_login() -> bool:
    """Enable macOS Remote Login via sudo. Returns True on success."""
    try:
        result = subprocess.run(
            ["sudo", "systemsetup", "-setremotelogin", "on"],
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0
    except Exception:
        return False


def ensure_ssh_directory() -> Path:
    """Create ~/.ssh with mode 700 if missing. Return the path."""
    ssh_dir = Path.home() / ".ssh"
    if not ssh_dir.exists():
        ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    else:
        # Enforce correct permissions (SSH refuses if too open)
        current_mode = oct(ssh_dir.stat().st_mode)[-3:]
        if current_mode != "700":
            ssh_dir.chmod(0o700)
    return ssh_dir


def ensure_local_ssh_key() -> Path | None:
    """
    Ensure a local SSH keypair exists (~/.ssh/id_ed25519).
    Returns the public key path on success, or None on failure.
    """
    ssh_dir = ensure_ssh_directory()
    private_key = ssh_dir / "id_ed25519"
    public_key = ssh_dir / "id_ed25519.pub"

    if public_key.exists() and private_key.exists():
        return public_key

    try:
        result = subprocess.run(
            [
                "ssh-keygen",
                "-t",
                "ed25519",
                "-N",
                "",
                "-f",
                str(private_key),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None
    except Exception:
        return None

    return public_key if public_key.exists() else None


def append_authorized_key(public_key: str) -> bool:
    """
    Append a public key to ~/.ssh/authorized_keys.
    Avoids duplicates. Returns True on success.
    """
    public_key = public_key.strip()
    if not validate_ssh_public_key(public_key):
        return False

    ssh_dir = ensure_ssh_directory()
    auth_keys = ssh_dir / "authorized_keys"

    # Check for duplicates
    if auth_keys.exists():
        existing = auth_keys.read_text(errors="replace")
        if public_key in existing:
            return True  # already present

    # Append
    with open(auth_keys, "a") as f:
        f.write(public_key + "\n")

    # Ensure correct permissions
    try:
        os.chmod(auth_keys, 0o600)
    except OSError:
        pass

    return True


class SSHSetup(ProvisioningStep):
    """
    Configures SSH remote access based on setup choices.

    Unlike most steps, this one doesn't install software — it configures
    the built-in macOS SSH server and authorized keys.
    """

    name = "SSH Remote Access"

    def __init__(
        self,
        enable_login: bool = False,
        authorized_key: str = "",
    ) -> None:
        self._enable_login = enable_login
        self._authorized_key = authorized_key.strip()

    # ── Interface ─────────────────────────────────────────────────────────────

    def is_installed(self) -> bool:
        # SSH is built into macOS; always "installed"
        return True

    def current_version(self) -> str | None:
        try:
            result = subprocess.run(
                ["ssh", "-V"], capture_output=True, text=True, timeout=10,
            )
            return result.stderr.strip() or result.stdout.strip() or None
        except Exception:
            return None

    def install(self) -> None:
        # No-op — SSH is an OS component
        pass

    # ── Orchestration override ────────────────────────────────────────────────

    def provision(self, dry_run: bool = False) -> bool:
        """Execute SSH setup actions based on configuration."""
        log.info(self._section_header())

        status = check_remote_login_status()
        log.info(f"  Remote Login (SSH): {status}")

        if dry_run:
            self._report_authorized_keys()
            return True

        success = True

        # Step 1: Enable Remote Login if requested
        if self._enable_login and status != "on":
            log.info("  Enabling Remote Login (SSH)...")
            if enable_remote_login():
                log.info("  Remote Login: enabled")
                key_path = ensure_local_ssh_key()
                if key_path is not None:
                    log.info(f"  Local SSH keypair ensured at: {key_path}")
                else:
                    log.warning("  Could not create local SSH keypair (id_ed25519)")
            else:
                log.error("  Failed to enable Remote Login")
                log.error("  Try manually: sudo systemsetup -setremotelogin on")
                success = False
        elif status == "on":
            log.info("  Remote Login already enabled — no action needed")

        # Step 2: Add authorized key if provided
        if self._authorized_key:
            if not validate_ssh_public_key(self._authorized_key):
                log.error("  Invalid SSH public key format — skipping")
                success = False
            else:
                ensure_ssh_directory()
                if append_authorized_key(self._authorized_key):
                    # Show a brief identifier for the key
                    parts = self._authorized_key.split()
                    comment = parts[2] if len(parts) >= 3 else parts[0][:20] + "..."
                    log.info(f"  Authorized key added: {comment}")
                else:
                    log.error("  Failed to add authorized key")
                    success = False

        self._report_authorized_keys()
        return success

    # ── Internal ──────────────────────────────────────────────────────────────

    def _report_authorized_keys(self) -> None:
        """Log the count of authorized keys."""
        auth_keys = Path.home() / ".ssh" / "authorized_keys"
        if auth_keys.exists():
            try:
                lines = auth_keys.read_text(errors="replace").splitlines()
                count = sum(
                    1 for line in lines
                    if line.strip() and not line.startswith("#")
                )
                log.info(f"  Authorized keys: {count} key(s) configured")
            except OSError as e:
                log.warning(f"  Could not read authorized_keys: {e}")
        else:
            log.info("  No authorized_keys file — add keys to allow SSH access")
