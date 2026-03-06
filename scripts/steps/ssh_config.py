"""
SSH configuration provisioning step.

Reports macOS Remote Login (sshd) status and ensures the ~/.ssh directory
exists with correct permissions. Does not enable Remote Login automatically —
that requires sudo and an explicit user decision. Instead, it logs the
command to enable it if not already active.
"""

from __future__ import annotations

import platform
from pathlib import Path
from typing import Optional

from . import ProvisioningStep, log, run


class SSHConfig(ProvisioningStep):
    """
    Checks SSH / Remote Login configuration on macOS.

    - is_installed(): always True on macOS (SSH is built in).
    - install():      no-op (SSH is part of the OS).
    - provision():    fully overridden to report-only; never makes system changes
                      except creating ~/.ssh with correct permissions.
    """

    name = "SSH"

    # ── Interface ─────────────────────────────────────────────────────────────

    def is_installed(self) -> bool:
        # SSH toolchain is built into macOS; it's always present.
        return platform.system() == "Darwin"

    def current_version(self) -> Optional[str]:
        result = run(["ssh", "-V"], check=False)
        # ssh -V writes to stderr
        return result.stderr.strip() or result.stdout.strip() or None

    def install(self) -> None:
        # SSH is a macOS OS component — nothing to install.
        log.info("  SSH is built into macOS — no installation required")

    # ── Orchestration override ────────────────────────────────────────────────

    def provision(self, dry_run: bool = False) -> bool:
        """
        Override: report SSH status and ensure ~/.ssh exists.
        Never modifies system SSH settings; only creates ~/.ssh if missing.
        """
        log.info(self._section_header())

        if platform.system() != "Darwin":
            log.info("  Not macOS — skipping SSH configuration check")
            return True

        try:
            self._check_remote_login()
            self._ensure_ssh_directory()
            return True
        except Exception as e:
            log.error(f"  SSH check failed: {e}")
            log.debug("  Stack trace:", exc_info=True)
            return False

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _check_remote_login(self) -> None:
        """Log the current Remote Login (sshd) status."""
        # Try passwordless sudo first (common in dev setups)
        result = run(
            ["sudo", "-n", "systemsetup", "-getremotelogin"],
            check=False,
            timeout=10,
        )
        if result.returncode == 0:
            status_line = result.stdout.strip().lower()
            if "on" in status_line:
                log.info("  Remote Login (SSH): enabled")
            else:
                log.info("  Remote Login (SSH): disabled")
                log.info("  To enable:  sudo systemsetup -setremotelogin on")
                log.info(
                    "  Or via GUI: System Settings → General → Sharing → Remote Login"
                )
            return

        # Fallback: check launchctl (no sudo required)
        result = run(
            ["launchctl", "list", "com.openssh.sshd"],
            check=False,
            timeout=10,
        )
        if result.returncode == 0:
            log.info("  Remote Login (SSH): enabled")
        else:
            log.info("  Remote Login (SSH): status unknown (sudo required for full check)")
            log.info("  Check via: System Settings → General → Sharing → Remote Login")

    def _ensure_ssh_directory(self) -> None:
        """Create ~/.ssh with mode 700 if missing; correct permissions if wrong."""
        ssh_dir = Path.home() / ".ssh"

        if not ssh_dir.exists():
            log.info("  Creating ~/.ssh with mode 700...")
            ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        else:
            # Enforce correct permissions (SSH refuses to use ~/.ssh if too open)
            current_mode = oct(ssh_dir.stat().st_mode)[-3:]
            if current_mode != "700":
                log.warning(f"  ~/.ssh permissions are {current_mode} — correcting to 700")
                ssh_dir.chmod(0o700)

        # Report authorized_keys status
        authorized_keys = ssh_dir / "authorized_keys"
        if authorized_keys.exists():
            try:
                lines = authorized_keys.read_text(errors="replace").splitlines()
                key_count = sum(
                    1 for line in lines if line.strip() and not line.startswith("#")
                )
                log.info(f"  Authorized keys: {key_count} key(s) configured")
            except OSError as e:
                log.warning(f"  Could not read authorized_keys: {e}")
        else:
            log.info(f"  No authorized_keys — add public keys to: {authorized_keys}")
