"""
llama-server (llama.cpp) service manager.

Manages llama-server instances for local LLM inference. Each instance is
launched as an independent process with configured args (model path,
GPU layers, context size, etc.). Health is checked via the /health endpoint.
"""

from __future__ import annotations

import logging
import shutil
from typing import Optional

from . import BaseService

log = logging.getLogger("llm-gateway")


class LlamaCppService(BaseService):
    """
    Manages a llama-server instance.

    Config example:
        binary: "llama-server"
        args:
          --model: "/models/qwen3-4b-q4_k_m.gguf"
          --host: "0.0.0.0"
          --port: "8081"
          --n-gpu-layers: "99"
          --ctx-size: "8192"
          --threads: "4"
          --parallel: "3"
        extra_args:
          - "--cont-batching"
          - "--flash-attn"
          - "--mlock"
    """

    service_type = "llamacpp"

    def _build_command(self) -> list[str]:
        binary = self.svc_config.get("binary", "llama-server")
        cmd = [binary]

        # Named args from the args dict
        args = self.svc_config.get("args", {})
        if isinstance(args, dict):
            for flag, value in args.items():
                if value is not None and str(value).strip():
                    cmd.append(str(flag))
                    cmd.append(str(value))

        # Extra positional/flag args
        extra = self.svc_config.get("extra_args", [])
        if isinstance(extra, list):
            cmd.extend(str(a) for a in extra if a)

        return cmd

    async def _post_start(self) -> None:
        """Verify the model file exists after start (for better error messages)."""
        args = self.svc_config.get("args", {})
        model_path = args.get("--model", "") if isinstance(args, dict) else ""
        if model_path and not _file_exists(model_path):
            log.warning(
                f"  [{self.name}] Model file may not exist: {model_path}. "
                f"The process may fail to load."
            )


def _file_exists(path: str) -> bool:
    """Check if a file exists (handles ~ expansion)."""
    from pathlib import Path
    try:
        return Path(path).expanduser().exists()
    except Exception:
        return False
