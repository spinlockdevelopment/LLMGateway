"""
Whisper speech-to-text service manager.

Supports both whisper-server (whisper.cpp) and mlx-openai-server
(MLX-optimized Whisper). The service type is determined by the configured
binary name. Both expose an OpenAI-compatible /v1/audio/transcriptions
endpoint that LiteLLM can route to.
"""

from __future__ import annotations

import logging

from . import BaseService

log = logging.getLogger("llm-gateway")


class WhisperService(BaseService):
    """
    Manages a Whisper speech-to-text server.

    Supported binaries:
      - whisper-server  (whisper.cpp, GGUF models)
      - mlx-openai-server (MLX-optimized, mlx-community models)

    Config example:
        binary: "whisper-server"
        args:
          --model: "/models/whisper/whisper-large-v3-turbo-q5_0.bin"
          --host: "0.0.0.0"
          --port: "8083"
          --threads: "2"
    """

    service_type = "whisper"

    def _build_command(self) -> list[str]:
        binary = self.svc_config.get("binary", "whisper-server")
        cmd = [binary]

        args = self.svc_config.get("args", {})
        if isinstance(args, dict):
            for flag, value in args.items():
                if value is not None and str(value).strip():
                    cmd.append(str(flag))
                    cmd.append(str(value))

        extra = self.svc_config.get("extra_args", [])
        if isinstance(extra, list):
            cmd.extend(str(a) for a in extra if a)

        return cmd
