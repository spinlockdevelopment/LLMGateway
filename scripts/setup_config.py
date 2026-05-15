"""
Initial setup choices for LLM Gateway.

Captures structural choices made during setup:
  - Data directory path
  - Which optional components to install (Ollama, llama.cpp, whisper)

Stored at: <data_dir>/setup-config.yaml
Read by: setup script (to provision), gw script (to filter components shown).

Secrets/API keys are NOT stored here — they live in .env (managed by the
admin UI). SSH configuration is handled separately by ssh-remote-setup.py.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class SetupConfig:
    """Structural setup choices (no secrets)."""

    data_dir: str = "~/.llm-gateway"
    install_ollama: bool = False
    install_llama_cpp: bool = False
    install_whisper: bool = False

    # ── Persistence ──────────────────────────────────────────────────────────

    @classmethod
    def load(cls, path: Path) -> SetupConfig:
        """Load from YAML file. Returns defaults if file doesn't exist."""
        if not path.exists():
            return cls()
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            return cls()
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self, path: Path) -> None:
        """Write to YAML file. Creates parent directories."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "data_dir": self.data_dir,
            "install_ollama": self.install_ollama,
            "install_llama_cpp": self.install_llama_cpp,
            "install_whisper": self.install_whisper,
        }
        path.write_text(
            yaml.dump(data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    # ── Helpers ───────────────────────────────────────────────────────────────

    def selected_components(self) -> list[str]:
        """Return list of selected optional component names."""
        result: list[str] = []
        if self.install_ollama:
            result.append("ollama")
        if self.install_llama_cpp:
            result.append("llama-server")
        if self.install_whisper:
            result.append("whisper-server")
        return result

    def generate_env_file(self, env_example_path: Path, output_path: Path) -> None:
        """
        Create .env from the .env.example template on first run.
        Existing .env files are left untouched (managed via the Secrets UI).
        """
        if output_path.exists():
            return
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if env_example_path.exists():
            shutil.copy2(env_example_path, output_path)
        else:
            output_path.write_text(
                "LITELLM_MASTER_KEY=sk-gateway-master-change-me\n"
                "DATABASE_URL=postgresql://litellm:litellm@postgres:5432/litellm\n",
                encoding="utf-8",
            )
        try:
            os.chmod(output_path, 0o600)
        except OSError:
            pass
