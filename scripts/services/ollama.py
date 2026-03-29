"""
Ollama service manager.

Uses the `ollama serve` process directly (no Homebrew services integration)
and monitors it via the HTTP API. If an Ollama server is already running
on the configured port when the gateway starts, this manager will detect it
and attach to it without starting a new process.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from . import BaseService, ServiceState

log = logging.getLogger("llm-gateway")


class OllamaService(BaseService):
    """
    Manages the Ollama inference server.

    Start priority: brew services > direct `ollama serve`.
    Health check: HTTP GET http://localhost:<port>/api/tags.
    Additional: supports model pull/list via the Ollama CLI.
    """

    service_type = "ollama"

    def _build_command(self) -> list[str]:
        binary = self.svc_config.get("binary", "ollama")
        return [binary, "serve"]

    # ── Lifecycle overrides ───────────────────────────────────────────────────

    async def start(self) -> bool:
        """
        Start Ollama using `ollama serve` when needed.

        If an Ollama server is already running and responding on the
        configured port, this method will not launch a new process and
        will instead attach to the existing server.
        """
        if self._state == ServiceState.DISABLED:
            return False

        # If an Ollama server is already up, just mark as running.
        if await self.health_check():
            log.debug(f"  [{self.name}] Already running and healthy")
            return True

        # Warn about common permission misconfiguration before starting.
        self.warn_if_owned_by_root()

        self._state = ServiceState.STARTING
        log.info(f"  [{self.name}] Starting Ollama via `ollama serve`...")
        return await super().start()

    async def stop(self) -> bool:
        if self._state in (ServiceState.STOPPED, ServiceState.DISABLED):
            return True
        return await super().stop()

    async def health_check(self) -> bool:
        """
        Check Ollama health via its HTTP API, independent of process tracking.
        """
        if not self.health_url:
            port = self.svc_config.get("port", 11434)
            self.health_url = f"http://localhost:{port}/api/tags"
        loop = asyncio.get_event_loop()
        try:
            code = await loop.run_in_executor(
                None, self._http_get_status, self.health_url
            )
            return 200 <= code < 400
        except Exception:
            return False

    # ── Ollama-specific operations ────────────────────────────────────────────

    async def pull_model(self, model_name: str) -> tuple[bool, str]:
        """
        Pull a model via `ollama pull`. Returns (success, output).
        Runs in a thread pool to avoid blocking the event loop.
        """
        binary = self.svc_config.get("binary", "ollama")
        if not shutil.which(binary):
            return False, f"Binary not found: {binary}"

        log.info(f"  [{self.name}] Pulling model: {model_name}")
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    [binary, "pull", model_name],
                    capture_output=True,
                    text=True,
                    timeout=1800,  # 30 minutes for large models
                ),
            )
            output = (result.stdout + "\n" + result.stderr).strip()
            if result.returncode == 0:
                log.info(f"  [{self.name}] Model pulled: {model_name}")
                return True, output
            else:
                log.error(f"  [{self.name}] Pull failed: {output[:300]}")
                return False, output
        except subprocess.TimeoutExpired:
            return False, "Pull timed out after 30 minutes"
        except Exception as e:
            return False, str(e)

    async def list_models(self) -> list[dict]:
        """Query Ollama API for available models."""
        if not self.health_url:
            return []

        port = self.svc_config.get("port", 11434)
        url = f"http://localhost:{port}/api/tags"

        loop = asyncio.get_event_loop()
        try:
            import urllib.request
            response_body = await loop.run_in_executor(
                None,
                lambda: urllib.request.urlopen(url, timeout=5).read().decode(),
            )
            data = json.loads(response_body)
            return data.get("models", [])
        except Exception:
            return []

    def warn_if_owned_by_root(self) -> None:
        """
        Log a warning if the Ollama data directory appears to be owned by root.

        This helps explain cases where Ollama prints that it must run as admin:
        the most common cause is that ~/.ollama was created by a root process,
        so a normal user cannot read/write its contents.
        """
        models_dir = self.svc_config.get("models_dir", "~/.ollama")
        expanded = Path(os.path.expanduser(models_dir))
        try:
            st = expanded.stat()
        except FileNotFoundError:
            return
        except OSError:
            return

        # On macOS/Linux, uid 0 is root.
        if st.st_uid == 0:
            log.warning(
                "  [ollama] Models directory %s is owned by root. "
                "Run `chown -R $(whoami) %s` or reinstall Ollama as the "
                "same user that runs the gateway to avoid permission issues.",
                expanded,
                expanded,
            )

    # Homebrew services integration intentionally removed; Ollama is launched
    # directly via the `ollama` CLI and monitored via HTTP.
