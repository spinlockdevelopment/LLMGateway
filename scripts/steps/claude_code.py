"""
Claude Code CLI provisioning step.

Installs @anthropic-ai/claude-code globally via npm and upgrades it
whenever a newer version is published to the npm registry.
"""

from __future__ import annotations

import json
from typing import Optional

from . import ProvisioningStep, command_exists, log, run

_PACKAGE = "@anthropic-ai/claude-code"


class ClaudeCode(ProvisioningStep):
    """
    Ensures the Claude Code CLI is installed globally via npm and up to date.

    - is_installed():    npm list -g confirms package is present.
    - current_version(): parsed from npm list --json output; falls back to
                         `claude --version` if json parsing fails.
    - latest_version():  npm view <pkg> version (npm registry).
    - install():         npm install -g <pkg>
    - upgrade():         npm update -g <pkg>
    """

    name = "Claude Code CLI"

    # ── Interface ─────────────────────────────────────────────────────────────

    def is_installed(self) -> bool:
        result = run(
            ["npm", "list", "-g", "--depth=0", _PACKAGE],
            check=False,
            timeout=30,
        )
        return result.returncode == 0 and _PACKAGE in result.stdout

    def current_version(self) -> Optional[str]:
        # Primary: parse structured JSON from npm list
        result = run(
            ["npm", "list", "-g", "--depth=0", "--json"],
            check=False,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            try:
                data = json.loads(result.stdout)
                pkg = data.get("dependencies", {}).get(_PACKAGE, {})
                ver = pkg.get("version")
                if ver:
                    return ver
            except (json.JSONDecodeError, KeyError):
                pass

        # Fallback: ask the CLI directly
        if command_exists("claude"):
            result = run(["claude", "--version"], check=False, timeout=15)
            if result.returncode == 0:
                return result.stdout.strip()

        return None

    def latest_version(self) -> Optional[str]:
        """Query the npm registry for the latest published version."""
        result = run(["npm", "view", _PACKAGE, "version"], check=False, timeout=30)
        if result.returncode == 0:
            return result.stdout.strip() or None
        return None

    def install(self) -> None:
        log.info(f"  Installing {_PACKAGE} globally via npm...")
        run(["npm", "install", "-g", _PACKAGE], timeout=180)
        if command_exists("claude"):
            result = run(["claude", "--version"], check=False)
            ver = result.stdout.strip() if result.returncode == 0 else "unknown"
            log.info(f"  Installed: {ver}")
        else:
            log.warning(
                "  'claude' not found on PATH after install — "
                "check your npm global bin directory is on PATH"
            )

    def upgrade(self) -> None:
        log.info(f"  Updating {_PACKAGE} via npm...")
        run(["npm", "update", "-g", _PACKAGE], check=False, timeout=120)
        ver = self.current_version()
        if ver:
            log.info(f"  Updated to: {ver}")

    # ── Already-installed hook ────────────────────────────────────────────────

    def _on_already_installed(self) -> None:
        current = self.current_version()
        latest = self.latest_version()
        if latest and current and latest.strip() != current.strip():
            log.info(f"  Upgrade available: {current} → {latest}")
            self.upgrade()
        else:
            log.info(
                f"  Up to date: {current}"
                + (f" (latest: {latest})" if latest else "")
            )
