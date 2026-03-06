"""
Shared utilities and abstract base class for LLM Gateway provisioning steps.

Each step class implements:
  - is_installed()     -> bool              Required
  - current_version()  -> Optional[str]     Required
  - install()          -> None              Required
  - latest_version()   -> Optional[str]     Optional (returns None by default)
  - upgrade()          -> None              Optional (defaults to install())
  - needs_upgrade()    -> bool              Optional (compares current vs latest)

Orchestration:
  - provision(dry_run=False) -> bool        Idempotent install/upgrade; safe to repeat
  - status()           -> dict              Structured status for programmatic use
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from abc import ABC, abstractmethod
from typing import Optional

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
    """
    Run a subprocess command, log it, and return the result.

    Args:
        cmd:     Command list or shell string.
        check:   Raise CalledProcessError on non-zero exit if True.
        capture: Capture stdout/stderr if True (required for reading output).
        shell:   Pass cmd to the shell if True.
        timeout: Kill the process after this many seconds.

    Raises:
        subprocess.CalledProcessError: If check=True and exit code != 0.
        subprocess.TimeoutExpired:     If the command exceeds timeout.
    """
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


# ── Base provisioning step ────────────────────────────────────────────────────

class ProvisioningStep(ABC):
    """
    Abstract base class for all provisioning steps.

    Subclasses MUST implement:
      - is_installed()    — True if the component is present on this system.
      - current_version() — Installed version string, or None.
      - install()         — Perform a fresh installation.

    Subclasses MAY override:
      - latest_version()        — Online version check. Default: None.
      - upgrade()               — Upgrade logic. Default: calls install().
      - needs_upgrade()         — True if upgrade is recommended.
      - _on_already_installed() — Hook called when component is already present.
      - provision()             — Full orchestration. Override for custom logic.
    """

    #: Human-readable label shown in log section headers.
    name: str = "unnamed"

    # ── Abstract interface ────────────────────────────────────────────────────

    @abstractmethod
    def is_installed(self) -> bool:
        """Return True if this component is present on the system."""

    @abstractmethod
    def current_version(self) -> Optional[str]:
        """Return the installed version string, or None if not installed."""

    @abstractmethod
    def install(self) -> None:
        """Perform a fresh installation from scratch."""

    # ── Overrideable hooks ────────────────────────────────────────────────────

    def latest_version(self) -> Optional[str]:
        """
        Return the latest available version string from an online source.
        Return None if the check is not implemented or unavailable.
        """
        return None

    def upgrade(self) -> None:
        """Upgrade to the latest version. Default: re-runs install()."""
        self.install()

    def needs_upgrade(self) -> bool:
        """
        Return True if an upgrade is recommended.
        Default: compare current vs latest; returns False if either is unknown.
        """
        current = self.current_version()
        latest = self.latest_version()
        if current and latest:
            return current.strip() != latest.strip()
        return False

    def _on_already_installed(self) -> None:
        """
        Called by provision() when the component is already installed.
        Default: check for upgrade and apply it if found.
        Subclasses override this for component-specific upgrade logic.
        """
        try:
            current = self.current_version()
            latest = self.latest_version()
            if latest and current and latest.strip() != current.strip():
                log.info(f"  Upgrade available: {current} → {latest}")
                self.upgrade()
                new_ver = self.current_version()
                log.info(f"  Upgraded to: {new_ver or 'ok'}")
            elif latest:
                log.info(f"  Up to date (latest: {latest})")
            else:
                log.info("  Already installed (version check not available)")
        except Exception as e:
            log.warning(f"  Version check/upgrade failed (non-fatal): {e}")

    # ── Section header helper ─────────────────────────────────────────────────

    def _section_header(self) -> str:
        """Return a fixed-width section header string for log output."""
        prefix = f"── {self.name} "
        return prefix + "─" * max(0, _HEADER_TOTAL_WIDTH - len(prefix))

    # ── Orchestration ─────────────────────────────────────────────────────────

    def provision(self, dry_run: bool = False) -> bool:
        """
        Idempotent provisioning entry point. Safe to call repeatedly.

        - If dry_run=True: report status only, make no changes.
        - If not installed: installs the component.
        - If installed: calls _on_already_installed() (upgrade check/etc).

        Returns:
            True on success (or if dry_run); False if provisioning failed.
        """
        log.info(self._section_header())
        try:
            if dry_run:
                self._report_status()
                return True

            if not self.is_installed():
                log.info("  Not installed — installing...")
                self.install()
                ver = self.current_version()
                log.info(f"  Installed: {ver or 'ok'}")
            else:
                ver = self.current_version()
                log.info(f"  Installed: {ver}")
                self._on_already_installed()

            return True

        except Exception as e:
            log.error(f"  Provisioning FAILED: {e}")
            log.debug("  Stack trace:", exc_info=True)
            return False

    def _report_status(self) -> None:
        """Log current and latest version without making any changes."""
        installed = self.is_installed()
        if not installed:
            log.info("  Status: NOT INSTALLED")
            latest = self.latest_version()
            if latest:
                log.info(f"  Latest available: {latest}")
            return

        current = self.current_version()
        latest = self.latest_version()
        log.info(f"  Installed: {current or 'unknown version'}")
        if latest:
            if current and current.strip() == latest.strip():
                log.info(f"  Latest:    {latest}  ✓ up to date")
            else:
                log.info(f"  Latest:    {latest}  ⚠ upgrade available")

    def status(self) -> dict:
        """Return a structured status dict for programmatic use."""
        installed = self.is_installed()
        current = self.current_version() if installed else None
        latest = self.latest_version()
        upgrade_available: Optional[bool] = None
        if current and latest:
            upgrade_available = current.strip() != latest.strip()
        return {
            "name": self.name,
            "installed": installed,
            "current_version": current,
            "latest_version": latest,
            "upgrade_available": upgrade_available,
        }
