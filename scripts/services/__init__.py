"""
Service lifecycle management for local inference processes.

Each service type (Ollama, llama-server, whisper-server) extends the
BaseService class and provides its own start/stop/health-check logic.

Services are launched as independent processes (not children of the gateway).
The ServiceRegistry owns the collection and runs the background health loop.
"""

from __future__ import annotations

import asyncio
import enum
import logging
import os
import signal
import shutil
import subprocess
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger("llm-gateway")


class ServiceState(str, enum.Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    UNHEALTHY = "unhealthy"
    STOPPING = "stopping"
    FAILED = "failed"
    DISABLED = "disabled"


@dataclass
class ServiceStatus:
    """Snapshot of a service's current status."""
    name: str
    state: ServiceState
    description: str = ""
    pid: Optional[int] = None
    port: Optional[int] = None
    health_url: Optional[str] = None
    uptime_sec: Optional[float] = None
    restart_count: int = 0
    last_error: Optional[str] = None
    expected_memory_gb: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.value,
            "description": self.description,
            "pid": self.pid,
            "port": self.port,
            "health_url": self.health_url,
            "uptime_sec": round(self.uptime_sec, 1) if self.uptime_sec else None,
            "restart_count": self.restart_count,
            "last_error": self.last_error,
            "expected_memory_gb": self.expected_memory_gb,
        }


class BaseService:
    """
    Abstract base for managed local inference services.

    Subclasses MUST implement:
      - _build_command() -> list[str]  — the command + args to launch.
      - service_type                   — class-level string identifier.

    Subclasses MAY override:
      - _post_start()    — hook called after process launch.
      - _pre_stop()      — hook called before SIGTERM.
      - health_check()   — custom health logic (default: HTTP GET).
    """

    service_type: str = "base"

    def __init__(self, name: str, svc_config: dict) -> None:
        self.name = name
        self.svc_config = svc_config
        self.description = svc_config.get("description", name)
        self.health_url: Optional[str] = svc_config.get("health_check_url")
        self.expected_memory_gb: float = svc_config.get("expected_memory_gb", 0.0)

        self._process: Optional[subprocess.Popen] = None
        self._pid: Optional[int] = None
        self._started_at: Optional[float] = None
        self._restart_count: int = 0
        self._last_error: Optional[str] = None
        self._state: ServiceState = ServiceState.STOPPED

        if not svc_config.get("enabled", False):
            self._state = ServiceState.DISABLED

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def state(self) -> ServiceState:
        return self._state

    @property
    def enabled(self) -> bool:
        return self._state != ServiceState.DISABLED

    @property
    def port(self) -> Optional[int]:
        """Extract port from config (top-level or in args)."""
        p = self.svc_config.get("port")
        if p is not None:
            return int(p)
        args = self.svc_config.get("args", {})
        if isinstance(args, dict):
            p = args.get("--port")
            if p is not None:
                return int(p)
        return None

    # ── Abstract method ───────────────────────────────────────────────────────

    def _build_command(self) -> list[str]:
        """Return the command list to start the service process."""
        raise NotImplementedError

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> bool:
        """
        Start the service process. Returns True if started successfully.
        Idempotent: returns True immediately if already running.
        """
        if self._state == ServiceState.DISABLED:
            log.debug(f"  [{self.name}] Disabled — skipping start")
            return False

        if self._state == ServiceState.RUNNING and self._is_process_alive():
            log.debug(f"  [{self.name}] Already running (pid {self._pid})")
            return True

        self._state = ServiceState.STARTING
        log.info(f"  [{self.name}] Starting...")

        try:
            cmd = self._build_command()
            binary = cmd[0]

            # Verify binary exists
            if not shutil.which(binary):
                raise FileNotFoundError(f"Binary not found: {binary}")

            env = {**os.environ, **self.svc_config.get("environment", {})}
            work_dir = self.svc_config.get("working_dir")

            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,    # detach from our process group
                env=env,
                cwd=work_dir,
            )
            self._pid = self._process.pid
            self._started_at = time.time()

            # Give it a moment to crash or bind its port
            await asyncio.sleep(2)

            if not self._is_process_alive():
                exit_code = self._process.poll()
                raise RuntimeError(
                    f"Process exited immediately (exit code {exit_code})"
                )

            await self._post_start()
            self._state = ServiceState.RUNNING
            log.info(f"  [{self.name}] Started (pid {self._pid})")
            return True

        except Exception as e:
            self._state = ServiceState.FAILED
            self._last_error = str(e)
            log.error(f"  [{self.name}] Failed to start: {e}")
            return False

    async def stop(self) -> bool:
        """Stop the service process gracefully. Returns True if stopped."""
        if self._state in (ServiceState.STOPPED, ServiceState.DISABLED):
            return True

        self._state = ServiceState.STOPPING
        log.info(f"  [{self.name}] Stopping (pid {self._pid})...")

        try:
            await self._pre_stop()

            if self._process and self._is_process_alive():
                # SIGTERM for graceful shutdown
                os.kill(self._pid, signal.SIGTERM)

                # Wait up to 10 seconds for graceful exit
                for _ in range(20):
                    if not self._is_process_alive():
                        break
                    await asyncio.sleep(0.5)
                else:
                    # Force kill if still alive
                    log.warning(f"  [{self.name}] SIGTERM timeout — sending SIGKILL")
                    os.kill(self._pid, signal.SIGKILL)
                    await asyncio.sleep(0.5)

            self._state = ServiceState.STOPPED
            self._process = None
            self._pid = None
            self._started_at = None
            log.info(f"  [{self.name}] Stopped")
            return True

        except ProcessLookupError:
            # Process already gone
            self._state = ServiceState.STOPPED
            self._process = None
            self._pid = None
            return True
        except Exception as e:
            self._last_error = str(e)
            log.error(f"  [{self.name}] Error stopping: {e}")
            return False

    async def restart(self) -> bool:
        """Stop then start the service. Returns True if restarted."""
        await self.stop()
        await asyncio.sleep(1)
        self._restart_count += 1
        return await self.start()

    # ── Health ────────────────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        """
        Return True if the service is healthy.
        Default: HTTP GET to health_check_url, expect 200.
        Falls back to process-alive check if no URL configured.
        """
        if not self._is_process_alive():
            return False

        if not self.health_url:
            return self._is_process_alive()

        loop = asyncio.get_event_loop()
        try:
            code = await loop.run_in_executor(None, self._http_get_status, self.health_url)
            return 200 <= code < 400
        except Exception:
            return False

    @staticmethod
    def _http_get_status(url: str, timeout: int = 5) -> int:
        """Synchronous HTTP GET — returns status code or raises."""
        req = urllib.request.Request(url, method="GET")
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.status

    # ── Status ────────────────────────────────────────────────────────────────

    def status(self) -> ServiceStatus:
        """Return a snapshot of the service's current state."""
        uptime = None
        if self._started_at and self._state == ServiceState.RUNNING:
            uptime = time.time() - self._started_at

        return ServiceStatus(
            name=self.name,
            state=self._state,
            description=self.description,
            pid=self._pid,
            port=self.port,
            health_url=self.health_url,
            uptime_sec=uptime,
            restart_count=self._restart_count,
            last_error=self._last_error,
            expected_memory_gb=self.expected_memory_gb,
        )

    # ── Internal ──────────────────────────────────────────────────────────────

    def _is_process_alive(self) -> bool:
        """Check if the managed process is still running."""
        if self._process is None:
            return False
        return self._process.poll() is None

    async def _post_start(self) -> None:
        """Hook called after the process is launched. Override in subclass."""
        pass

    async def _pre_stop(self) -> None:
        """Hook called before sending SIGTERM. Override in subclass."""
        pass


class ServiceRegistry:
    """
    Holds all managed services and runs the background health monitor.
    """

    def __init__(self, health_config: dict) -> None:
        self._services: dict[str, BaseService] = {}
        self._health_config = health_config
        self._monitor_task: Optional[asyncio.Task] = None

    @property
    def services(self) -> dict[str, BaseService]:
        return dict(self._services)

    def register(self, service: BaseService) -> None:
        self._services[service.name] = service
        log.debug(f"  Registered service: {service.name} ({service.service_type})")

    def get(self, name: str) -> Optional[BaseService]:
        return self._services.get(name)

    async def start_all(self) -> None:
        """Start all enabled services."""
        for svc in self._services.values():
            if svc.enabled and svc.svc_config.get("auto_start", True):
                await svc.start()

    async def stop_all(self) -> None:
        """Stop all running services (reverse order)."""
        for svc in reversed(list(self._services.values())):
            if svc.state not in (ServiceState.STOPPED, ServiceState.DISABLED):
                await svc.stop()

    def start_health_monitor(self) -> None:
        """Start the background health check loop."""
        if self._monitor_task is None or self._monitor_task.done():
            self._monitor_task = asyncio.create_task(self._health_loop())
            log.info("  Health monitor started")

    def stop_health_monitor(self) -> None:
        """Cancel the background health check loop."""
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            log.info("  Health monitor stopped")

    async def _health_loop(self) -> None:
        """Periodically health-check all running services."""
        interval = self._health_config.get("interval_sec", 15)
        max_restarts = self._health_config.get("max_restart_attempts", 5)
        delay = self._health_config.get("restart_delay_sec", 5)
        backoff = self._health_config.get("restart_backoff_multiplier", 1.5)

        while True:
            try:
                await asyncio.sleep(interval)

                for svc in self._services.values():
                    if svc.state not in (ServiceState.RUNNING, ServiceState.UNHEALTHY):
                        continue

                    healthy = await svc.health_check()

                    if healthy and svc.state == ServiceState.UNHEALTHY:
                        svc._state = ServiceState.RUNNING
                        log.info(f"  [{svc.name}] Recovered — now healthy")
                    elif not healthy and svc.state == ServiceState.RUNNING:
                        svc._state = ServiceState.UNHEALTHY
                        log.warning(f"  [{svc.name}] Health check failed — UNHEALTHY")
                    elif not healthy and svc.state == ServiceState.UNHEALTHY:
                        # Already unhealthy — attempt restart if within limits
                        if max_restarts == 0 or svc._restart_count < max_restarts:
                            wait = delay * (backoff ** svc._restart_count)
                            log.warning(
                                f"  [{svc.name}] Restarting "
                                f"(attempt {svc._restart_count + 1}, "
                                f"wait {wait:.0f}s)..."
                            )
                            await asyncio.sleep(wait)
                            await svc.restart()
                        else:
                            svc._state = ServiceState.FAILED
                            log.error(
                                f"  [{svc.name}] Max restart attempts "
                                f"({max_restarts}) exceeded — FAILED"
                            )

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"  Health monitor error: {e}")
                await asyncio.sleep(interval)

    def all_status(self) -> list[dict]:
        """Return status dicts for all registered services."""
        return [svc.status().to_dict() for svc in self._services.values()]
