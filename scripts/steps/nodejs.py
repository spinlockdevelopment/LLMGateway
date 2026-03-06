"""
Node.js + npm provisioning step.

Installs Node.js via Homebrew, enforces a minimum major version (18+),
and keeps npm itself updated to latest after any install or upgrade.
"""

from __future__ import annotations

import json
from typing import Optional

from . import ProvisioningStep, command_exists, log, run

_MIN_NODE_MAJOR = 18


class NodeJS(ProvisioningStep):
    """
    Ensures Node.js (18+) and npm are installed and current.

    - install():  brew install node  + npm update
    - upgrade():  brew upgrade node  + npm update
    - _on_already_installed(): enforces minimum version, checks brew outdated,
                               always refreshes npm.
    """

    name = "Node.js"

    # ── Interface ─────────────────────────────────────────────────────────────

    def is_installed(self) -> bool:
        return command_exists("node")

    def current_version(self) -> Optional[str]:
        if not self.is_installed():
            return None
        result = run(["node", "--version"], check=False)
        return result.stdout.strip() if result.returncode == 0 else None

    def latest_version(self) -> Optional[str]:
        """Query Homebrew for the latest stable Node.js version."""
        if not command_exists("brew"):
            return None
        result = run(["brew", "info", "--json=v2", "node"], check=False, timeout=30)
        if result.returncode != 0:
            return None
        try:
            data = json.loads(result.stdout)
            formulae = data.get("formulae", [])
            if formulae:
                stable = formulae[0].get("versions", {}).get("stable")
                return f"v{stable}" if stable else None
        except (json.JSONDecodeError, KeyError, IndexError):
            pass
        return None

    def install(self) -> None:
        log.info("  Installing Node.js via Homebrew...")
        run(["brew", "install", "node"], timeout=300)
        self._update_npm()

    def upgrade(self) -> None:
        log.info("  Upgrading Node.js via Homebrew...")
        run(["brew", "upgrade", "node"], check=False, timeout=300)
        self._update_npm()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _node_major(self) -> Optional[int]:
        """Parse the major version number from the installed Node.js version."""
        ver = self.current_version()
        if not ver:
            return None
        try:
            return int(ver.lstrip("v").split(".")[0])
        except (ValueError, IndexError):
            return None

    def _update_npm(self) -> None:
        """Update npm to latest globally (non-fatal if it fails)."""
        if not command_exists("npm"):
            log.warning("  npm not found on PATH after node install")
            return
        log.info("  Updating npm to latest...")
        run(["npm", "install", "-g", "npm@latest"], check=False, timeout=120)
        result = run(["npm", "--version"], check=False)
        if result.returncode == 0:
            log.info(f"  npm: {result.stdout.strip()}")

    # ── Already-installed hook ────────────────────────────────────────────────

    def _on_already_installed(self) -> None:
        major = self._node_major()

        # Enforce minimum major version
        if major is not None and major < _MIN_NODE_MAJOR:
            log.info(
                f"  Node.js v{major} is below minimum (v{_MIN_NODE_MAJOR}) — upgrading..."
            )
            self.upgrade()
            return

        # Check Homebrew for a newer formula version
        result = run(["brew", "outdated", "node"], check=False, timeout=30)
        if result.returncode == 0 and result.stdout.strip():
            log.info("  Node.js upgrade available via Homebrew — upgrading...")
            self.upgrade()
        else:
            latest = self.latest_version()
            log.info(
                f"  Node.js: up to date{f' (latest: {latest})' if latest else ''}"
            )
            # Always keep npm current regardless of node upgrade
            self._update_npm()
