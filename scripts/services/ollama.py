"""
Ollama service manager.

Ollama on macOS is best managed via `brew services` which registers it
with launchd for auto-start and crash recovery. This manager uses
brew services when available, falling back to direct process launch.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import subprocess
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
        if self._state == ServiceState.DISABLED:
            return False
        if self._state == ServiceState.RUNNING and await self.health_check():
            log.debug(f"  [{self.name}] Already running and healthy")
            return True

        self._state = ServiceState.STARTING
        log.info(f"  [{self.name}] Starting Ollama...")

        # Prefer brew services (launchd-managed, auto-restart on crash)
        if self._use_brew_services():
            return await self._start_via_brew()

        # Fallback: direct process launch
        return await super().start()

    async def stop(self) -> bool:
        if self._state in (ServiceState.STOPPED, ServiceState.DISABLED):
            return True

        if self._use_brew_services():
            return await self._stop_via_brew()

        return await super().stop()

    async def health_check(self) -> bool:
        """Check Ollama health via its API endpoint."""
        if not self.health_url:
            port = self.svc_config.get("port", 11434)
            self.health_url = f"http://localhost:{port}/api/tags"
        return await super().health_check()

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

    # ── brew services integration ─────────────────────────────────────────────

    @staticmethod
    def _use_brew_services() -> bool:
        """Return True if brew services is available and Ollama is a brew formula."""
        if not shutil.which("brew"):
            return False
        result = subprocess.run(
            ["brew", "list", "ollama"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0

    async def _start_via_brew(self) -> bool:
        """Start Ollama via brew services (launchd-managed)."""
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    ["brew", "services", "start", "ollama"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                ),
            )
            if result.returncode != 0:
                err = result.stderr.strip() or result.stdout.strip()
                # "already started" is not an error
                if "already started" not in err.lower():
                    raise RuntimeError(f"brew services start failed: {err}")

            # Wait for the API to respond
            for _ in range(20):
                await asyncio.sleep(1)
                if await self.health_check():
                    self._state = ServiceState.RUNNING
                    log.info(f"  [{self.name}] Started via brew services")
                    return True

            self._state = ServiceState.UNHEALTHY
            log.warning(f"  [{self.name}] Started but health check not responding")
            return True  # process may be starting slowly

        except Exception as e:
            self._state = ServiceState.FAILED
            self._last_error = str(e)
            log.error(f"  [{self.name}] brew services start failed: {e}")
            return False

    async def _stop_via_brew(self) -> bool:
        """Stop Ollama via brew services."""
        self._state = ServiceState.STOPPING
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    ["brew", "services", "stop", "ollama"],
                    capture_output=True,
                    timeout=30,
                ),
            )
            self._state = ServiceState.STOPPED
            log.info(f"  [{self.name}] Stopped via brew services")
            return True
        except Exception as e:
            self._last_error = str(e)
            log.error(f"  [{self.name}] brew services stop failed: {e}")
            return False
