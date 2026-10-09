#!/usr/bin/env python3
"""
LLM Gateway — Management Service
=================================
Central management daemon for the LLM Gateway stack on macOS.

Responsibilities:
  - Web UI dashboard (config editor, service status)
  - Read-only REST API for programmatic status queries
  - Lifecycle management for local inference services (llama-server,
    whisper-server) with health monitoring and automatic restart
  - launchd self-registration for auto-start at login

Usage:
    python3 scripts/llmgateway.py                  # run the service
    python3 scripts/llmgateway.py --install         # register as launchd agent
    python3 scripts/llmgateway.py --uninstall       # remove launchd agent
    python3 scripts/llmgateway.py --status          # CLI status check (no server)

    # Run provisioning (headless, no web UI):
    python3 scripts/setup-llmgateway.py
    python3 scripts/setup-llmgateway.py --status
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import platform
import signal
import sys
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).parent.resolve()
_REPO_DIR = _SCRIPT_DIR.parent.resolve()
sys.path.insert(0, str(_SCRIPT_DIR))

_LOG_FORMAT = "%(asctime)s [%(levelname)-8s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _setup_logging(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("llm-gateway")
    logger.setLevel(logging.DEBUG)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(getattr(logging, level.upper(), logging.INFO))
    console.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
    logger.addHandler(console)

    # macOS syslog (best-effort)
    try:
        from logging.handlers import SysLogHandler
        syslog = SysLogHandler(address="/var/run/syslog")
        syslog.setLevel(logging.INFO)
        syslog.setFormatter(logging.Formatter("llm-gateway: [%(levelname)s] %(message)s"))
        logger.addHandler(syslog)
    except Exception:
        pass

    return logger


def _load_config():
    """Return (ConfigManager, data_dir): repo defaults + data-dir overrides."""
    from config.manager import ConfigManager
    from data_dir import get_data_dir

    data_dir = get_data_dir()
    cm = ConfigManager(_REPO_DIR / "config", user_config_dir=data_dir / "config")
    cm.load()
    return cm, data_dir


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_install(log: logging.Logger) -> int:
    """Register the gateway as a macOS launchd agent."""
    from launchd.manager import install
    from cli_symlink import install_symlink

    _, data_dir = _load_config()
    ok = install(repo_dir=_REPO_DIR, data_dir=data_dir)
    if ok:
        log.info("Launch agent installed. The gateway will start on next login.")
        log.info("To start now: launchctl load ~/Library/LaunchAgents/com.local.llm-gateway.plist")
    # Best-effort: add `gw` to PATH. Failure does not fail the install.
    install_symlink(_REPO_DIR)
    return 0 if ok else 1


def cmd_uninstall(log: logging.Logger) -> int:
    """Remove the launchd agent."""
    from launchd.manager import uninstall
    from cli_symlink import uninstall_symlink
    ok = uninstall()
    uninstall_symlink(_REPO_DIR)
    return 0 if ok else 1


def cmd_status(log: logging.Logger) -> int:
    """Print status to stdout without starting the server."""
    import psutil
    from launchd.manager import status as launchd_status
    from steps.ssh_setup import check_remote_login_status

    cm, _ = _load_config()

    log.info("=" * 52)
    log.info("  LLM Gateway — Status")
    log.info("=" * 52)
    log.info(f"  Python:       {sys.version.split()[0]}")
    log.info(f"  Platform:     {platform.platform()}")
    log.info(f"  Architecture: {platform.machine()}")
    log.info(f"  Repo:         {_REPO_DIR}")

    ssh_status = check_remote_login_status()
    if ssh_status == "on":
        ssh_display = "enabled"
    elif ssh_status == "off":
        ssh_display = "disabled"
    else:
        ssh_display = "unknown"
    log.info(f"  Remote SSH:   {ssh_display}")

    # Memory
    mem = psutil.virtual_memory()
    log.info(f"  Memory:       {mem.used / (1024**3):.1f} / {mem.total / (1024**3):.1f} GB ({mem.percent}%)")

    # launchd
    ld = launchd_status()
    log.info(f"  Launch agent: {'loaded' if ld['loaded'] else 'installed' if ld['installed'] else 'not installed'}")

    # Services
    services_config = cm.config.get("services", {})
    log.info("")
    log.info("  Services:")
    for name, svc_cfg in services_config.items():
        enabled = svc_cfg.get("enabled", False)
        svc_type = svc_cfg.get("type", "?")
        desc = svc_cfg.get("description", "")
        status_str = "enabled" if enabled else "disabled"
        log.info(f"    {name:20s} [{svc_type:10s}] {status_str:10s} {desc}")

    log.info("=" * 52)
    return 0


async def cmd_serve(log: logging.Logger) -> int:
    """Start the web UI, REST API, and service manager."""
    from services import Service, ServiceRegistry
    from web import create_app

    cm, data_dir = _load_config()

    gateway_cfg = cm.config.get("gateway", {})
    host = gateway_cfg.get("host", "127.0.0.1")
    port = gateway_cfg.get("port", 8080)
    log_level = gateway_cfg.get("log_level", "INFO")

    # Adjust log level from config
    for handler in log.handlers:
        if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
            handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Build service registry
    health_config = cm.config.get("health_check", {})
    registry = ServiceRegistry(health_config)

    services_config = cm.config.get("services", {})
    for name, svc_cfg in services_config.items():
        registry.register(Service(name, svc_cfg))

    # Reconcile litellm-config.yaml with .env: add search_tools entries for
    # any web-search API key (Tavily/Exa/Brave/Serper) that's set but not yet
    # wired up. Idempotent and non-destructive — never removes entries.
    try:
        from web.ui import sync_search_tools_with_env
        added = sync_search_tools_with_env(_REPO_DIR, data_dir)
        if added:
            log.info(f"  Auto-added search_tools at startup: {', '.join(added)}")
    except Exception:
        log.warning("  search_tools sync at startup failed", exc_info=True)

    # Create FastAPI app
    app = create_app(cm, registry, _REPO_DIR, data_dir=data_dir)

    # Banner
    log.info("=" * 52)
    log.info("  LLM Gateway — Starting")
    log.info("=" * 52)
    log.info(f"  Dashboard:    http://{host}:{port}")
    log.info(f"  REST API:     http://{host}:{port}/api/status")
    log.info(f"  Config dir:   {_REPO_DIR / 'config'}")
    log.info(f"  Data dir:     {data_dir}")
    svc_count = sum(1 for s in registry.services.values() if s.enabled)
    log.info(f"  Services:     {svc_count} enabled / {len(registry.services)} configured")
    log.info("=" * 52)
    log.info("")

    # Start managed services
    await registry.start_all()
    registry.start_health_monitor()

    # Graceful shutdown handler
    shutdown_event = asyncio.Event()

    def _signal_handler(sig, frame):
        log.info(f"  Received signal {sig} — shutting down...")
        shutdown_event.set()

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    # Run uvicorn
    import uvicorn

    # Force uvicorn's own loggers to use the daemon's format so every line in
    # gateway.log carries a timestamp and level — uvicorn's default handlers
    # emit bare "INFO:     message" lines with neither.
    uvicorn_log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "uniform": {"format": _LOG_FORMAT, "datefmt": _DATE_FORMAT},
        },
        "handlers": {
            "uniform": {
                "class": "logging.StreamHandler",
                "formatter": "uniform",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "uvicorn":        {"handlers": ["uniform"], "level": log_level.upper(), "propagate": False},
            "uvicorn.error":  {"handlers": ["uniform"], "level": log_level.upper(), "propagate": False},
            "uvicorn.access": {"handlers": ["uniform"], "level": log_level.upper(), "propagate": False},
        },
    }

    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level=log_level.lower(),
        access_log=False,
        log_config=uvicorn_log_config,
    )
    server = uvicorn.Server(config)

    # Run server in a task so we can also watch for shutdown
    server_task = asyncio.create_task(server.serve())

    # Wait for either server exit or shutdown signal
    done, _ = await asyncio.wait(
        [server_task, asyncio.create_task(shutdown_event.wait())],
        return_when=asyncio.FIRST_COMPLETED,
    )

    # Cleanup
    log.info("  Stopping services...")
    registry.stop_health_monitor()
    await registry.stop_all()

    if not server_task.done():
        server.should_exit = True
        with contextlib.suppress(asyncio.CancelledError):
            await server_task

    log.info("  LLM Gateway stopped.")
    return 0


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="LLM Gateway — management service (web UI + service manager)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--install",
        action="store_true",
        help="Register as a macOS launchd agent (auto-starts on login)",
    )
    group.add_argument(
        "--uninstall",
        action="store_true",
        help="Remove the launchd agent",
    )
    group.add_argument(
        "--status",
        action="store_true",
        help="Print service status to stdout (no server started)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug-level logging",
    )
    args = parser.parse_args()

    log = _setup_logging("DEBUG" if args.verbose else "INFO")

    if args.install:
        return cmd_install(log)
    elif args.uninstall:
        return cmd_uninstall(log)
    elif args.status:
        return cmd_status(log)
    else:
        return asyncio.run(cmd_serve(log))


if __name__ == "__main__":
    sys.exit(main())
