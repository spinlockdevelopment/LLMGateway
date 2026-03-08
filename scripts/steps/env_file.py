"""
Environment file (.env) provisioning step.

Copies .env.example to .env on first run so the stack has a configuration
file to read. Warns prominently if placeholder values remain, since the
stack will fail to authenticate against providers without real API keys.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import ProvisioningStep, log

# Values that indicate the .env has not been configured by the user.
_PLACEHOLDER_MARKERS = (
    "your-key-here",
    "change-me",
    "YOUR_KEY",
    "REPLACE_ME",
    "sk-xxxx",
    "changeme",
)


class EnvFile(ProvisioningStep):
    """
    Ensures a .env file exists in the repository root.

    - is_installed():    True if .env exists.
    - current_version(): last-modified timestamp of .env (proxy for "version").
    - install():         copies .env.example → .env (warns about placeholder values).
    - _on_already_installed(): warns if placeholder values are still present.
    """

    name = "Environment File (.env)"

    def __init__(self, repo_dir: Path) -> None:
        self.repo_dir = repo_dir
        self._env_file = repo_dir / ".env"
        self._env_example = repo_dir / ".env.example"

    # ── Interface ─────────────────────────────────────────────────────────────

    def is_installed(self) -> bool:
        return self._env_file.exists()

    def current_version(self) -> Optional[str]:
        if not self._env_file.exists():
            return None
        mtime = self._env_file.stat().st_mtime
        return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")

    def install(self) -> None:
        if not self._env_example.exists():
            log.warning(f"  .env.example not found at {self._env_example}")
            log.warning("  Create .env manually with your API keys")
            return

        log.info(f"  Copying .env.example → .env")
        shutil.copy2(self._env_example, self._env_file)
        log.warning("  .env created from example — edit it with API keys you need:")
        log.warning(f"    {self._env_file}")
        log.warning("  Set LITELLM_MASTER_KEY for proxy admin and virtual keys; add provider keys (e.g. OPENROUTER_API_KEY) as needed.")

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _has_placeholders(self) -> bool:
        """Return True if .env still contains any known placeholder strings."""
        try:
            content = self._env_file.read_text(errors="replace")
            return any(marker in content for marker in _PLACEHOLDER_MARKERS)
        except OSError:
            return False

    # ── Already-installed hook ────────────────────────────────────────────────

    def _on_already_installed(self) -> None:
        log.info(f"  .env: {self._env_file}")
        if self._has_placeholders():
            log.warning("  .env contains placeholder values!")
            log.warning(
                "  Edit .env and set real values for any keys you use "
                "(e.g. LITELLM_MASTER_KEY, OPENROUTER_API_KEY)"
            )
        else:
            log.info("  .env: configured (no placeholder values detected)")
