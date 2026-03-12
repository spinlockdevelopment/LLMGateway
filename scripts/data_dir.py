"""
Data directory discovery for LLM Gateway.

The data directory stores runtime state that should survive repo deletion:
  - .env (secrets / API keys)
  - config/llmgateway.yaml (user config overrides)
  - logs/ (management service stdout/stderr)
  - backups/ (config backups)
  - setup-config.yaml (initial setup choices)

Default: ~/.llm-gateway/
Override: set LLM_GATEWAY_DATA_DIR environment variable.

Zero external dependencies — safe for system Python (gw script).
"""

from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_DATA_DIR = Path.home() / ".llm-gateway"
_ENV_VAR = "LLM_GATEWAY_DATA_DIR"


# ── Core discovery ───────────────────────────────────────────────────────────

def get_data_dir() -> Path:
    """
    Return the resolved data directory path.

    Priority: LLM_GATEWAY_DATA_DIR env var → ~/.llm-gateway/
    """
    env_val = os.environ.get(_ENV_VAR, "").strip()
    if env_val:
        return Path(env_val).expanduser().resolve()
    return _DEFAULT_DATA_DIR


def ensure_data_dir() -> Path:
    """Create the data directory structure if it doesn't exist. Return the path."""
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "config").mkdir(exist_ok=True)
    (data_dir / "logs").mkdir(exist_ok=True)
    (data_dir / "backups").mkdir(exist_ok=True)
    return data_dir


# ── Path helpers ─────────────────────────────────────────────────────────────

def env_path() -> Path:
    """Path to the .env secrets file."""
    return get_data_dir() / ".env"


def user_config_path() -> Path:
    """Path to the user config overrides YAML."""
    return get_data_dir() / "config" / "llmgateway.yaml"


def setup_config_path() -> Path:
    """Path to the initial setup preferences file."""
    return get_data_dir() / "setup-config.yaml"


def log_dir() -> Path:
    """Path to the log directory."""
    return get_data_dir() / "logs"


def backups_dir() -> Path:
    """Path to the backups directory."""
    return get_data_dir() / "backups"
