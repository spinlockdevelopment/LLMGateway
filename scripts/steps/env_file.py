"""
Environment file (.env) provisioning step.

Copies .env.example to .env on first run so the stack has a configuration
file to read.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from . import info, success, warn, provision

_PLACEHOLDER_MARKERS = (
    "your-key-here",
    "change-me",
    "YOUR_KEY",
    "REPLACE_ME",
    "sk-xxxx",
    "changeme",
)


def setup(repo_dir: Path, data_dir: Path, dry_run: bool = False) -> bool:
    """Ensure .env exists in the data directory."""
    env_file = data_dir / ".env"
    env_example = repo_dir / ".env.example"

    def is_ready() -> bool:
        return env_file.exists()

    def install() -> None:
        if not env_example.exists():
            warn(f".env.example not found at {env_example}")
            warn("Create .env manually with your API keys")
            return
        env_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(env_example, env_file)
        success(f".env created from template: {env_file}")
        warn(".env created from template — add your API keys")

    ok = provision(
        name="Environment File (.env)",
        is_ready=is_ready,
        install=install,
        dry_run=dry_run,
    )

    # Warn about placeholders even if file already existed
    if env_file.exists():
        try:
            content = env_file.read_text(errors="replace")
            if any(m in content for m in _PLACEHOLDER_MARKERS):
                warn(".env contains placeholder values — update via dashboard Secrets tab")
        except OSError:
            pass

    return ok
