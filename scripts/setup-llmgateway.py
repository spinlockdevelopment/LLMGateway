#!/usr/bin/env python3
"""
LLM Gateway — Setup Script
==========================
Provisions all components required for the LLM Gateway stack on macOS
(Apple Silicon). Safe to run on every boot — every step is idempotent.

Components provisioned (in order):
  1. Git                   — version check and repo pull
  2. Node.js + npm         — Homebrew, minimum v18
  3. Claude Code CLI       — global npm package
  4. Docker Desktop        — Homebrew cask, daemon readiness
  5. Ollama                — bare metal Homebrew (Metal GPU)
  6. SSH                   — Remote Login status, ~/.ssh directory
  7. Environment File      — .env from .env.example (first run)
  8. Docker Compose Stack  — launch if not running, health checks

Usage:
    ./bootstrap-llmgateway.sh   # start gateway (or --status / --install)
    python3 scripts/setup-llmgateway.py   # normal provisioning
    python3 scripts/setup-llmgateway.py --status   # status check only (no changes)
"""

from __future__ import annotations

import argparse
import logging
import platform
import sys
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
# This script lives in <repo>/provisioning/. Add that directory to sys.path
# so that `from steps.xxx import Xxx` resolves correctly.
_SCRIPT_DIR = Path(__file__).parent.resolve()
_REPO_DIR = _SCRIPT_DIR.parent.resolve()
sys.path.insert(0, str(_SCRIPT_DIR))

# ── Logging ───────────────────────────────────────────────────────────────────
_LOG_FORMAT = "%(asctime)s [%(levelname)-8s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure the provisioning logger with console and optional syslog output."""
    logger = logging.getLogger("llm-gateway-provision")
    logger.setLevel(logging.DEBUG)

    # Console handler — info by default, debug in verbose mode
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    console.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
    logger.addHandler(console)

    # macOS syslog — best-effort, non-fatal if unavailable
    try:
        from logging.handlers import SysLogHandler
        syslog = SysLogHandler(address="/var/run/syslog")
        syslog.setLevel(logging.INFO)
        syslog.setFormatter(
            logging.Formatter("llm-gateway-provision: [%(levelname)s] %(message)s")
        )
        logger.addHandler(syslog)
    except Exception:
        pass  # syslog not available (non-macOS, or socket missing)

    return logger


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "LLM Gateway setup — provisions all stack components on macOS. "
            "Safe to run repeatedly; all steps are idempotent."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help=(
            "Report installed versions and status for each component. "
            "Makes no changes to the system."
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show debug-level output (subprocess commands, raw output).",
    )
    args = parser.parse_args()

    log = _setup_logging(verbose=args.verbose)
    dry_run = args.status

    # ── Banner ────────────────────────────────────────────────────────────────
    log.info("=" * 52)
    mode_label = "Status Check" if dry_run else "Provisioning"
    log.info(f"  LLM Gateway — {mode_label}")
    log.info("=" * 52)
    log.info(f"  Python:       {sys.version.split()[0]}")
    log.info(f"  Platform:     {platform.platform()}")
    log.info(f"  Architecture: {platform.machine()}")
    log.info(f"  Repo:         {_REPO_DIR}")
    if dry_run:
        log.info("  Mode:         status check (no changes will be made)")
    log.info("")

    # ── Import steps ──────────────────────────────────────────────────────────
    # Imported inside main() so the logger is configured before any step module
    # code runs (step modules retrieve the logger at import time).
    try:
        from steps.git_repo import GitRepo
        from steps.nodejs import NodeJS
        from steps.claude_code import ClaudeCode
        from steps.docker import DockerDesktop
        from steps.ollama import Ollama
        from steps.ssh_config import SSHConfig
        from steps.env_file import EnvFile
        from steps.docker_stack import DockerStack
    except ImportError as e:
        log.error(f"Failed to import provisioning steps: {e}")
        log.error("Ensure you are running from the repository root or via bootstrap-llmgateway.sh")
        return 1

    # ── Step sequence ─────────────────────────────────────────────────────────
    steps = [
        GitRepo(repo_dir=_REPO_DIR),
        NodeJS(),
        ClaudeCode(),
        DockerDesktop(),
        Ollama(),
        SSHConfig(),
        EnvFile(repo_dir=_REPO_DIR),
        DockerStack(repo_dir=_REPO_DIR),
    ]

    failures: list[str] = []
    for step in steps:
        ok = step.provision(dry_run=dry_run)
        log.info("")  # blank line between sections
        if not ok:
            failures.append(step.name)

    # ── Summary ───────────────────────────────────────────────────────────────
    log.info("=" * 52)

    if dry_run:
        log.info("  Status check complete.")
        log.info("=" * 52)
        return 0

    if failures:
        log.error(f"  Provisioning completed with failures:")
        for name in failures:
            log.error(f"    ✗ {name}")
        log.error("")
        log.error("  Fix the issues above and re-run: python3 scripts/setup-llmgateway.py")
        log.info("=" * 52)
        return 1

    log.info("  Provisioning complete!  All components are ready.")
    log.info("")
    log.info("  Next steps (if not already done):")
    log.info("    1. Edit .env with your real API keys:")
    log.info(f"         {_REPO_DIR / '.env'}")
    log.info("    2. Start Ollama server:   ollama serve")
    log.info("    3. Pull a local model:    ollama pull llama3.2:3b")
    log.info("")
    log.info("  Stack endpoints:")
    log.info("    LiteLLM Proxy:  http://localhost:4000")
    log.info("    LiteLLM UI:     http://localhost:4000/ui")
    log.info("    Grafana:        http://localhost:3000")
    log.info("    Prometheus:     http://localhost:9090")
    log.info("=" * 52)
    return 0


if __name__ == "__main__":
    sys.exit(main())
