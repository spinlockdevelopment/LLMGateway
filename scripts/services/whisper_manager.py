"""
Standalone Whisper speech-to-text process manager.

No BaseService or ServiceRegistry dependency. Manages the whisper-server
(whisper.cpp) or mlx-openai-server process lifecycle directly.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import subprocess
import time
import urllib.request
from typing import Optional

log = logging.getLogger("llm-gateway")

# Valid state strings
STOPPED = "stopped"
STARTING = "starting"
RUNNING = "running"
FAILED = "failed"
STOPPING = "stopping"
DISABLED = "disabled"


class WhisperManager:
    """
    Standalone process manager for Whisper speech-to-text servers.

    Supports whisper-server (whisper.cpp) and mlx-openai-server.
    Does not inherit from BaseService or interact with ServiceRegistry.

    Config keys:
        enabled (bool): Whether the service is active.
        binary (str): Executable name, default "whisper-server".
        args (dict): Flag→value pairs passed to the binary.
        extra_args (list): Additional positional args appended after flags.
        health_check_url (str): URL for HTTP health checks.
    """

    def __init__(self, config: dict) -> None:
        self._config = config
        self._process: Optional[subprocess.Popen] = None
        self._pid: Optional[int] = None
        self._started_at: Optional[float] = None
        self._restart_count: int = 0
        self._last_error: Optional[str] = None

        if not config.get("enabled", False):
            self._state: str = DISABLED
        else:
            self._state = STOPPED

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def state(self) -> str:
        return self._state

    @property
    def enabled(self) -> bool:
        return self._state != DISABLED

    @property
    def health_url(self) -> Optional[str]:
        return self._config.get("health_check_url")

    # ── Command building ───────────────────────────────────────────────────────

    def _build_command(self) -> list[str]:
        binary = self._config.get("binary", "whisper-server")
        cmd = [binary]

        args = self._config.get("args", {})
        if isinstance(args, dict):
            for flag, value in args.items():
                if value is not None and str(value).strip():
                    cmd.append(str(flag))
                    cmd.append(str(value))

        extra = self._config.get("extra_args", [])
        if isinstance(extra, list):
            cmd.extend(str(a) for a in extra if a)

        return cmd

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> bool:
        """Launch the whisper process. Returns True if started successfully."""
        if self._state == DISABLED:
            log.debug("  [whisper] Disabled — skipping start")
            return False

        if self._state == RUNNING and self._is_process_alive():
            log.debug(f"  [whisper] Already running (pid {self._pid})")
            return True

        self._state = STARTING
        log.info("  [whisper] Starting...")

        try:
            cmd = self._build_command()
            env = {**os.environ, **self._config.get("environment", {})}
            work_dir = self._config.get("working_dir")

            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                env=env,
                cwd=work_dir,
            )
            self._pid = self._process.pid
            self._started_at = time.time()

            await asyncio.sleep(2)

            if not self._is_process_alive():
                exit_code = self._process.poll()
                raise RuntimeError(
                    f"Process exited immediately (exit code {exit_code})"
                )

            self._state = RUNNING
            log.info(f"  [whisper] Started (pid {self._pid})")
            return True

        except Exception as e:
            self._state = FAILED
            self._last_error = str(e)
            log.error(f"  [whisper] Failed to start: {e}")
            return False

    async def stop(self) -> bool:
        """Stop the process gracefully. Returns True if stopped."""
        if self._state in (STOPPED, DISABLED):
            return True

        self._state = STOPPING
        log.info(f"  [whisper] Stopping (pid {self._pid})...")

        try:
            if self._process and self._is_process_alive():
                os.kill(self._pid, signal.SIGTERM)

                for _ in range(20):
                    if not self._is_process_alive():
                        break
                    await asyncio.sleep(0.5)
                else:
                    log.warning("  [whisper] SIGTERM timeout — sending SIGKILL")
                    os.kill(self._pid, signal.SIGKILL)
                    await asyncio.sleep(0.5)

            self._state = STOPPED
            self._process = None
            self._pid = None
            self._started_at = None
            log.info("  [whisper] Stopped")
            return True

        except ProcessLookupError:
            self._state = STOPPED
            self._process = None
            self._pid = None
            return True
        except Exception as e:
            self._last_error = str(e)
            log.error(f"  [whisper] Error stopping: {e}")
            return False

    async def restart(self) -> bool:
        """Stop then start the process. Returns True if restarted."""
        await self.stop()
        await asyncio.sleep(1)
        self._restart_count += 1
        return await self.start()

    # ── Health ────────────────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        """
        Return True if the process is healthy.
        HTTP GET to health_url if configured, otherwise process-alive check.
        """
        if not self._is_process_alive():
            return False

        if not self.health_url:
            return True

        loop = asyncio.get_event_loop()
        try:
            code = await loop.run_in_executor(None, self._http_get_status, self.health_url)
            return 200 <= code < 400
        except Exception:
            return False

    @staticmethod
    def _http_get_status(url: str, timeout: int = 5) -> int:
        req = urllib.request.Request(url, method="GET")
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.status

    # ── Status ────────────────────────────────────────────────────────────────

    def status_dict(self) -> dict:
        """Return a plain dict snapshot of current state."""
        uptime = None
        if self._started_at and self._state == RUNNING:
            uptime = round(time.time() - self._started_at, 1)

        return {
            "name": "whisper",
            "state": self._state,
            "pid": self._pid,
            "uptime": uptime,
            "restart_count": self._restart_count,
            "last_error": self._last_error,
            "health_url": self.health_url,
        }

    # ── Internal ──────────────────────────────────────────────────────────────

    def _is_process_alive(self) -> bool:
        if self._process is None:
            return False
        return self._process.poll() is None
