"""
Ollama (local LLM runtime) provisioning step.

Installs Ollama on bare metal via Homebrew so it can use Apple Metal GPU
acceleration. Reports server status and loaded models if the server is
already running. Does NOT start the server automatically (ollama serve
is a long-running foreground process best managed by the user or launchd).
"""

from __future__ import annotations

import json
from typing import Optional

from . import ProvisioningStep, command_exists, log, run

_API_BASE = "http://localhost:11434"


class Ollama(ProvisioningStep):
    """
    Ensures Ollama is installed on bare metal for Apple Metal GPU acceleration.

    - install():  brew install ollama
    - upgrade():  brew upgrade ollama
    - _on_already_installed(): checks brew outdated, upgrades if available,
                               reports server status and loaded models.
    """

    name = "Ollama"

    # ── Interface ─────────────────────────────────────────────────────────────

    def is_installed(self) -> bool:
        return command_exists("ollama")

    def current_version(self) -> Optional[str]:
        if not self.is_installed():
            return None
        result = run(["ollama", "--version"], check=False)
        if result.returncode == 0:
            return result.stdout.strip() or result.stderr.strip() or None
        return None

    def latest_version(self) -> Optional[str]:
        """Query Homebrew for the latest available Ollama formula version."""
        if not command_exists("brew"):
            return None
        result = run(["brew", "info", "--json=v2", "ollama"], check=False, timeout=30)
        if result.returncode != 0:
            return None
        try:
            data = json.loads(result.stdout)
            formulae = data.get("formulae", [])
            if formulae:
                return formulae[0].get("versions", {}).get("stable")
        except (json.JSONDecodeError, KeyError, IndexError):
            pass
        return None

    def install(self) -> None:
        log.info("  Installing Ollama via Homebrew (bare metal — Metal GPU enabled)...")
        run(["brew", "install", "ollama"], timeout=300)
        log.info("  Ollama installed")
        log.info("  Start server:  ollama serve")
        log.info("  Pull a model:  ollama pull llama3.2:3b")

    def upgrade(self) -> None:
        log.info("  Upgrading Ollama via Homebrew...")
        run(["brew", "upgrade", "ollama"], check=False, timeout=300)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def is_running(self) -> bool:
        """Return True if the Ollama API server is responding."""
        result = run(
            ["curl", "-sf", f"{_API_BASE}/api/tags"],
            check=False,
            timeout=5,
        )
        return result.returncode == 0

    def _report_models(self) -> None:
        """Log models currently available in the Ollama server."""
        result = run(
            ["curl", "-sf", f"{_API_BASE}/api/tags"],
            check=False,
            timeout=10,
        )
        if result.returncode != 0:
            return
        try:
            data = json.loads(result.stdout)
            models = [m.get("name", "?") for m in data.get("models", [])]
            if models:
                log.info(f"  Available models: {', '.join(models[:10])}")
            else:
                log.info("  No models pulled yet — run: ollama pull llama3.2:3b")
        except (json.JSONDecodeError, KeyError):
            pass

    # ── Already-installed hook ────────────────────────────────────────────────

    def _on_already_installed(self) -> None:
        # Check Homebrew for a newer formula version
        result = run(["brew", "outdated", "ollama"], check=False, timeout=30)
        if result.returncode == 0 and result.stdout.strip():
            log.info("  Ollama upgrade available via Homebrew — upgrading...")
            self.upgrade()
            log.info(f"  Upgraded to: {self.current_version()}")
        else:
            log.info("  Ollama: up to date")

        # Report server status
        if self.is_running():
            log.info(f"  Server: running ({_API_BASE})")
            self._report_models()
        else:
            log.info("  Server: not running")
            log.info("  Start with: ollama serve")
