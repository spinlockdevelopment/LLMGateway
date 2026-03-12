"""
Configuration manager for LLM Gateway.

Handles loading, saving, validation, and defaults for the gateway config file.
The user config (llmgateway.yaml) overlays the shipped defaults
(llmgateway.defaults.yaml). Saving always writes to the user config file.

Secrets (.env) are handled separately — they are never written to YAML.
"""

from __future__ import annotations

import copy
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml

from .schema import validate_config

log = logging.getLogger("llm-gateway")

_DEFAULTS_FILENAME = "llmgateway.defaults.yaml"
_USER_FILENAME = "llmgateway.yaml"
_BACKUP_SUFFIX = ".bak"
_MAX_BACKUPS = 5


def _deep_merge(base: dict, override: dict) -> dict:
    """
    Recursively merge *override* into *base* (non-destructive).
    Returns a new dict; neither input is mutated.
    """
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


class ConfigManager:
    """
    Manages the gateway configuration lifecycle.

    - Loads shipped defaults + user overrides (deep-merged).
    - Validates on load and before save.
    - Keeps timestamped backups on save.
    - Provides reset-to-defaults.
    """

    def __init__(
        self,
        config_dir: Path,
        user_config_dir: Path | None = None,
    ) -> None:
        """
        Args:
            config_dir:      Directory containing llmgateway.defaults.yaml (ships with repo).
            user_config_dir: Directory for llmgateway.yaml user overrides and backups.
                             Defaults to config_dir for backward compatibility.
                             Typically set to <data_dir>/config/ so user config
                             survives repo deletion.
        """
        self._config_dir = config_dir
        self._user_config_dir = user_config_dir or config_dir
        self._defaults_path = config_dir / _DEFAULTS_FILENAME
        self._user_path = self._user_config_dir / _USER_FILENAME
        self._defaults: dict = {}
        self._config: dict = {}

    # ── Public interface ──────────────────────────────────────────────────────

    @property
    def config(self) -> dict:
        """Return the current merged configuration (read-only copy)."""
        return copy.deepcopy(self._config)

    @property
    def defaults(self) -> dict:
        """Return shipped defaults (read-only copy)."""
        return copy.deepcopy(self._defaults)

    @property
    def user_path(self) -> Path:
        return self._user_path

    def load(self) -> list[str]:
        """
        Load defaults + user config (if present). Returns validation warnings.
        Creates user config from defaults on first run.
        """
        # Load shipped defaults (required)
        if not self._defaults_path.exists():
            raise FileNotFoundError(
                f"Defaults file not found: {self._defaults_path}"
            )
        self._defaults = self._load_yaml(self._defaults_path)
        log.info(f"  Loaded defaults from {self._defaults_path}")

        # Load user overrides (optional — created from defaults on first run)
        if self._user_path.exists():
            user_config = self._load_yaml(self._user_path)
            self._config = _deep_merge(self._defaults, user_config)
            log.info(f"  Loaded user config from {self._user_path}")
        else:
            self._config = copy.deepcopy(self._defaults)
            log.info("  No user config found — using defaults")
            self._save_initial_config()

        # Validate
        errors, warnings = validate_config(self._config)
        if errors:
            for err in errors:
                log.error(f"  Config error: {err}")
            raise ValueError(
                f"Configuration has {len(errors)} error(s): {'; '.join(errors)}"
            )
        for warn in warnings:
            log.warning(f"  Config warning: {warn}")

        return warnings

    def save(self, new_config: dict) -> tuple[list[str], list[str]]:
        """
        Validate and save new config. Returns (errors, warnings).
        If errors is non-empty, nothing is written.
        Creates a timestamped backup of the previous file.
        """
        errors, warnings = validate_config(new_config)
        if errors:
            return errors, warnings

        # Backup existing file
        if self._user_path.exists():
            self._create_backup()

        # Write
        self._save_yaml(self._user_path, new_config)
        self._secure_file(self._user_path)

        # Reload merged config
        self._config = _deep_merge(self._defaults, new_config)
        log.info(f"  Config saved to {self._user_path}")

        return [], warnings

    def save_raw_yaml(self, yaml_text: str) -> tuple[list[str], list[str]]:
        """
        Parse, validate, and save raw YAML text from the UI editor.
        Returns (errors, warnings). If errors is non-empty, nothing is written.
        """
        try:
            parsed = yaml.safe_load(yaml_text)
        except yaml.YAMLError as e:
            return [f"YAML syntax error: {e}"], []

        if not isinstance(parsed, dict):
            return ["Config must be a YAML mapping (dict), not a scalar or list"], []

        return self.save(parsed)

    def reset_to_defaults(self) -> None:
        """Delete user config and reload from defaults only."""
        if self._user_path.exists():
            self._create_backup()
            self._user_path.unlink()
            log.info("  User config removed — reset to defaults")
        self._config = copy.deepcopy(self._defaults)

    def get_yaml_text(self) -> str:
        """Return the user config as a YAML string for the editor."""
        if self._user_path.exists():
            return self._user_path.read_text(encoding="utf-8")
        return yaml.dump(
            self._defaults, default_flow_style=False, sort_keys=False, width=120
        )

    def get_config_masked(self) -> dict:
        """Return config with any secret-looking values masked."""
        return self._mask_secrets(copy.deepcopy(self._config))

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _load_yaml(self, path: Path) -> dict:
        """Load and parse a YAML file. Returns empty dict on parse failure."""
        try:
            text = path.read_text(encoding="utf-8")
            data = yaml.safe_load(text)
            return data if isinstance(data, dict) else {}
        except yaml.YAMLError as e:
            log.error(f"  Failed to parse {path}: {e}")
            raise
        except OSError as e:
            log.error(f"  Failed to read {path}: {e}")
            raise

    def _save_yaml(self, path: Path, data: dict) -> None:
        """Write a dict to a YAML file."""
        text = yaml.dump(data, default_flow_style=False, sort_keys=False, width=120)
        path.write_text(text, encoding="utf-8")

    def _save_initial_config(self) -> None:
        """Create the initial user config file from the defaults template."""
        if self._defaults_path.exists():
            self._user_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self._defaults_path, self._user_path)
            self._secure_file(self._user_path)
            log.info(f"  Created initial config: {self._user_path}")

    def _create_backup(self) -> None:
        """Create a timestamped backup of the user config file."""
        if not self._user_path.exists():
            return
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = self._user_path.with_suffix(f".{timestamp}{_BACKUP_SUFFIX}")
        shutil.copy2(self._user_path, backup)
        log.debug(f"  Backup created: {backup}")
        self._prune_backups()

    def _prune_backups(self) -> None:
        """Keep only the most recent N backups."""
        pattern = f"{_USER_FILENAME}.*{_BACKUP_SUFFIX}"
        backups = sorted(self._user_config_dir.glob(pattern), reverse=True)
        for old in backups[_MAX_BACKUPS:]:
            old.unlink(missing_ok=True)

    @staticmethod
    def _secure_file(path: Path) -> None:
        """Set file permissions to owner-only read/write (chmod 600)."""
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass  # Windows or permission issue — non-fatal

    @staticmethod
    def _mask_secrets(data: Any, _depth: int = 0) -> Any:
        """Recursively mask values whose keys look like secrets."""
        if _depth > 20:
            return data
        secret_substrings = ("key", "secret", "password", "token", "credential")
        if isinstance(data, dict):
            masked = {}
            for k, v in data.items():
                key_lower = str(k).lower()
                if any(s in key_lower for s in secret_substrings) and isinstance(v, str) and len(v) > 4:
                    masked[k] = v[:2] + "****" + v[-2:]
                else:
                    masked[k] = ConfigManager._mask_secrets(v, _depth + 1)
            return masked
        if isinstance(data, list):
            return [ConfigManager._mask_secrets(item, _depth + 1) for item in data]
        return data
