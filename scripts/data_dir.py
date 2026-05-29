"""
Data directory discovery for LLM Gateway.

The data directory stores runtime state that should survive repo deletion
AND a full OS wipe. It lives on an external/dedicated volume so a fresh
macOS install can re-attach to it and restore the gateway end-to-end.

Layout:
  <data_dir>/
    .env                          (secrets / API keys)
    config/llmgateway.yaml        (user config overrides)
    litellm-config.yaml           (LiteLLM proxy routes; synced to repo copy)
    setup-config.yaml             (initial setup choices)
    logs/                         (management service stdout/stderr)
    backups/                      (config backups)
    venv/                         (mlx_audio.server host venv)
    hf-cache/                     (HF_HOME — Kokoro/MLX-Whisper downloads)
    docker-volumes/{postgres,open-webui,grafana,prometheus,loki}
                                  (bind-mounted from docker-compose.yml)

Default: /opt/storage/llmgateway/
Override: set LLM_GATEWAY_DATA_DIR environment variable.

Zero external dependencies — safe for system Python (gw script).
"""

from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_DATA_DIR = Path("/opt/storage/llmgateway")
_ENV_VAR = "LLM_GATEWAY_DATA_DIR"


# ── Core discovery ───────────────────────────────────────────────────────────

def get_data_dir() -> Path:
    """
    Return the resolved data directory path.

    Priority: LLM_GATEWAY_DATA_DIR env var → /opt/storage/llmgateway/
    """
    env_val = os.environ.get(_ENV_VAR, "").strip()
    if env_val:
        # Keep symlinks intact (no resolve()): /opt/storage -> /Volumes/External2T
        # must stay as /opt/storage in the launchd plist, because macOS launchd
        # refuses to open StandardOutPath under /Volumes/* for user LaunchAgents.
        return Path(env_val).expanduser().absolute()
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


def litellm_config_path() -> Path:
    """Path to the LiteLLM configuration file."""
    return get_data_dir() / "litellm-config.yaml"
