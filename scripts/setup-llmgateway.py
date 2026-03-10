#!/usr/bin/env python3
"""
LLM Gateway — Setup Script
==========================
Provisions all application-level components for the LLM Gateway stack on
macOS (Apple Silicon). Safe to run on every boot — every step is idempotent.

This script does NOT require admin/root privileges. If run as root, it
warns the user and asks for confirmation before continuing.

Components provisioned (in order):
  1. Git              — version check and repo pull
  2. Node.js + npm    — Homebrew, minimum v18
  3. Claude Code CLI  — global npm package
  4. Docker Desktop   — ensure daemon is running
  5. Environment File — .env from .env.example (first run)
  6. Docker Stack     — pull images and start compose services
  7. Ollama           — optional, prompted (bare metal, Metal GPU)
  8. llama-server     — optional, prompted (llama.cpp via Homebrew)
  9. whisper-server   — optional, prompted (whisper.cpp via Homebrew)
  10. SSH key          — optional, prompted
  11. Management Console — install + start as launchd service

Usage:
    python3 scripts/setup-llmgateway.py            # interactive provisioning
    python3 scripts/setup-llmgateway.py --status    # status check only
    python3 scripts/setup-llmgateway.py --verbose   # debug-level output
"""

from __future__ import annotations

import argparse
import logging
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).parent.resolve()
_REPO_DIR = _SCRIPT_DIR.parent.resolve()
sys.path.insert(0, str(_SCRIPT_DIR))

# ── Logging ───────────────────────────────────────────────────────────────────
_LOG_FORMAT = "%(asctime)s [%(levelname)-8s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure the provisioning logger."""
    logger = logging.getLogger("llm-gateway-provision")
    logger.setLevel(logging.DEBUG)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    console.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
    logger.addHandler(console)

    # macOS syslog — best-effort
    try:
        from logging.handlers import SysLogHandler
        syslog = SysLogHandler(address="/var/run/syslog")
        syslog.setLevel(logging.INFO)
        syslog.setFormatter(
            logging.Formatter("llm-gateway-provision: [%(levelname)s] %(message)s")
        )
        logger.addHandler(syslog)
    except Exception:
        pass

    return logger


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_root() -> bool:
    """Return True if running as root/admin."""
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False  # Windows doesn't have geteuid


def _prompt_yes_no(question: str, default: bool = True) -> bool:
    """
    Prompt the user with a yes/no question.
    Returns the default if input is empty or non-interactive.
    """
    suffix = " [Y/n]: " if default else " [y/N]: "
    try:
        answer = input(question + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    if not answer:
        return default
    return answer in ("y", "yes")


def _install_brew_formula(
    log: logging.Logger, formula: str, binary_name: str = ""
) -> bool:
    """
    Install a Homebrew formula if its binary is not already on PATH.
    Returns True if the binary is available after this call.
    """
    check_name = binary_name or formula
    if shutil.which(check_name):
        # Already installed — report version
        result = subprocess.run(
            [check_name, "--version"],
            capture_output=True, text=True, timeout=10,
        )
        version = result.stdout.strip() or result.stderr.strip() or "installed"
        log.info(f"  {check_name}: {version}")
        return True

    if not shutil.which("brew"):
        log.warning(f"  Cannot install {formula} — Homebrew not found")
        return False

    log.info(f"  Installing {formula} via Homebrew...")
    try:
        subprocess.run(["brew", "install", formula], check=True, timeout=600)
        log.info(f"  {formula}: installed")
        return True
    except subprocess.CalledProcessError as e:
        log.error(f"  Failed to install {formula}: {e}")
    except subprocess.TimeoutExpired:
        log.error(f"  Timed out installing {formula}")
    return False


def _install_management_console(log: logging.Logger) -> bool:
    """
    Register the management console as a launchd agent and start it.
    Returns True if the service was installed and started successfully.
    """
    try:
        # Import the launchd manager (available because scripts/ is on sys.path)
        from launchd.manager import install as launchd_install, is_loaded
        from config.manager import ConfigManager

        # Read gateway config for the port
        config_dir = _REPO_DIR / "config"
        cm = ConfigManager(config_dir)
        cm.load()
        port = cm.config.get("gateway", {}).get("port", 8080)

        log.info(f"  Registering management console on port {port}...")
        ok = launchd_install(repo_dir=_REPO_DIR, port=port)
        if not ok:
            log.error("  Failed to install launchd agent")
            return False

        # Give the agent a moment to start, then verify
        time.sleep(3)
        if is_loaded():
            log.info("  Management console: running")

            # Quick health check on the port
            try:
                result = subprocess.run(
                    ["curl", "-sf", f"http://localhost:{port}/api/status"],
                    capture_output=True, text=True, timeout=10,
                )
                if result.returncode == 0:
                    log.info(f"  Dashboard: http://localhost:{port}  ✓")
                else:
                    log.info(f"  Dashboard: http://localhost:{port}  (still starting...)")
            except Exception:
                log.info(f"  Dashboard: http://localhost:{port}  (still starting...)")
        else:
            log.warning("  Launchd agent installed but not yet loaded")
            log.info("  Start manually: launchctl load ~/Library/LaunchAgents/com.local.llm-gateway.plist")

        return True

    except ModuleNotFoundError as e:
        log.error(f"  Missing dependency: {e}")
        log.error("  Ensure you're running from the venv:")
        log.error(f"    {_REPO_DIR / '.venv/bin/python3'} scripts/setup-llmgateway.py")
        return False
    except Exception as e:
        log.error(f"  Management console setup failed: {e}")
        log.debug("  Stack trace:", exc_info=True)
        return False


# ── Virtual environment check ─────────────────────────────────────────────────

def _ensure_venv() -> None:
    """
    Verify we're running inside the project's .venv virtual environment.

    If not in the venv but it exists on disk, re-exec using the venv Python.
    If the venv doesn't exist at all, print instructions and exit.
    """
    venv_dir = _REPO_DIR / ".venv"
    venv_python = venv_dir / "bin" / "python3"

    # Same-file check first: venv/bin/python3 is often a symlink to system Python;
    # resolve() would point outside .venv and wrongly trigger re-exec in a loop.
    if venv_python.exists():
        try:
            if Path(sys.executable).samefile(venv_python):
                return
        except OSError:
            pass

    # Check if the current interpreter path lives inside the expected venv
    try:
        current_exe = Path(sys.executable).resolve()
        current_exe.relative_to(venv_dir.resolve())
        return
    except (ValueError, OSError):
        pass

    # Not in the venv — try to re-exec with the venv Python
    if venv_python.exists():
        resolved = str(venv_python.resolve())
        print(f"[setup] Not running in project venv — re-launching with {resolved}")
        try:
            os.execv(resolved, [resolved] + sys.argv)
        except OSError as e:
            print(f"ERROR: Cannot exec venv Python ({resolved}): {e}")
            print("The virtual environment may be corrupted. Delete .venv and re-run bootstrap.")
            sys.exit(1)
        # execv replaces the current process; we never reach here

    # Venv doesn't exist at all — fail with clear instructions
    print("ERROR: Project virtual environment not found at:")
    print(f"  {venv_dir}")
    print("")
    print("Run the bootstrap script first to create it:")
    print("  ./bootstrap-llmgateway.sh")
    print("")
    print("Or create it manually:")
    print(f"  python3 -m venv {venv_dir}")
    print(f"  {venv_python} -m pip install -r requirements.txt")
    sys.exit(1)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    # ── Venv gate ──────────────────────────────────────────────────────────
    # Must run inside the project venv so all dependencies are available.
    _ensure_venv()

    parser = argparse.ArgumentParser(
        description=(
            "LLM Gateway setup — provisions stack components on macOS. "
            "Safe to run repeatedly; all steps are idempotent. "
            "Does NOT require admin privileges."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Report status for each component (no changes made).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show debug-level output.",
    )
    args = parser.parse_args()

    log = _setup_logging(verbose=args.verbose)
    dry_run = args.status

    # ── Admin/root check ───────────────────────────────────────────────────
    # This setup script should NOT need root. Warn if elevated.
    if _is_root() and not dry_run:
        log.warning("")
        log.warning("  *** WARNING: Running as root/admin ***")
        log.warning("  This setup script does not require elevated privileges.")
        log.warning("  Running as root can cause file ownership issues.")
        log.warning("")
        if not _prompt_yes_no("  Continue as root anyway?", default=False):
            log.info("  Exiting. Re-run without sudo:")
            log.info("    python3 scripts/setup-llmgateway.py")
            return 1
        log.info("")

    # ── Banner ─────────────────────────────────────────────────────────────
    log.info("=" * 52)
    mode_label = "Status Check" if dry_run else "Setup"
    log.info(f"  LLM Gateway — {mode_label}")
    log.info("=" * 52)
    log.info(f"  Python:       {sys.version.split()[0]}")
    log.info(f"  Platform:     {platform.platform()}")
    log.info(f"  Architecture: {platform.machine()}")
    log.info(f"  Repo:         {_REPO_DIR}")
    if dry_run:
        log.info("  Mode:         status check (no changes will be made)")
    log.info("")

    # ── Import provisioning steps ──────────────────────────────────────────
    try:
        from steps.git_repo import GitRepo
        from steps.nodejs import NodeJS
        from steps.claude_code import ClaudeCode
        from steps.docker import DockerDesktop
        from steps.docker_stack import DockerStack
        from steps.ollama import Ollama
        from steps.ssh_config import SSHConfig
        from steps.env_file import EnvFile
    except ImportError as e:
        log.error(f"Failed to import provisioning steps: {e}")
        log.error("Ensure you are running from the repository root.")
        return 1

    # ── Core steps (always run) ────────────────────────────────────────────
    # These are required components that are not optional.
    core_steps = [
        GitRepo(repo_dir=_REPO_DIR),
        NodeJS(),
        ClaudeCode(),
        DockerDesktop(),
        EnvFile(repo_dir=_REPO_DIR),
        DockerStack(repo_dir=_REPO_DIR),
    ]

    failures: list[str] = []
    for step in core_steps:
        ok = step.provision(dry_run=dry_run)
        log.info("")  # blank line between sections
        if not ok:
            failures.append(step.name)

    # ── Optional steps (prompted) ──────────────────────────────────────────
    # Each optional component asks the user before installing.
    # In --status mode, just report without prompting.

    if not dry_run:
        log.info("=" * 52)
        log.info("  Optional Components")
        log.info("=" * 52)
        log.info("  You can skip any of these and install them later.")
        log.info("")

        # --- Ollama (local LLM runtime) ---
        if _prompt_yes_no("  Install/check Ollama (local LLM runtime)?"):
            ok = Ollama().provision(dry_run=False)
            log.info("")
            if not ok:
                failures.append("Ollama")
        else:
            log.info("  Skipping Ollama.")
            log.info("  Install later: brew install ollama")
            log.info("")

        # --- llama-server (llama.cpp) ---
        if _prompt_yes_no("  Install llama-server (llama.cpp for GGUF models)?"):
            log.info("  Checking llama-server...")
            if not _install_brew_formula(log, "llama.cpp", binary_name="llama-server"):
                failures.append("llama-server")
            log.info("")
        else:
            log.info("  Skipping llama-server.")
            log.info("  Install later: brew install llama.cpp")
            log.info("")

        # --- whisper-server (speech-to-text) ---
        if _prompt_yes_no("  Install whisper-server (speech-to-text)?"):
            log.info("  Checking whisper-server...")
            if not _install_brew_formula(
                log, "whisper-cpp", binary_name="whisper-server"
            ):
                failures.append("whisper-server")
            log.info("")
        else:
            log.info("  Skipping whisper-server.")
            log.info("  Install later: brew install whisper-cpp")
            log.info("")

        # --- SSH key ---
        if _prompt_yes_no("  Set up SSH key (~/.ssh)?"):
            ok = SSHConfig().provision(dry_run=False)
            log.info("")
            if not ok:
                failures.append("SSH")
        else:
            log.info("  Skipping SSH setup.")
            log.info("")

    else:
        # Status mode: report all components without prompting
        optional_status_steps = [
            Ollama(),
            SSHConfig(),
        ]
        for step in optional_status_steps:
            ok = step.provision(dry_run=True)
            log.info("")

    # ── Management Console ─────────────────────────────────────────────────
    # Install and start the management console as a background service.
    if not dry_run:
        log.info("=" * 52)
        log.info("  Management Console")
        log.info("=" * 52)
        log.info("")
        log.info("  The management console provides a web dashboard for")
        log.info("  config editing, secrets management, and service control.")
        log.info("")
        if not _install_management_console(log):
            failures.append("Management Console")
        log.info("")

    # ── Summary ────────────────────────────────────────────────────────────
    log.info("=" * 52)

    if dry_run:
        log.info("  Status check complete.")
        log.info("=" * 52)
        return 0

    if failures:
        log.error("  Setup completed with failures:")
        for name in failures:
            log.error(f"    ✗ {name}")
        log.error("")
        log.error("  Fix the issues above and re-run:")
        log.error("    python3 scripts/setup-llmgateway.py")
        log.info("=" * 52)
        return 1

    # ── Post-setup instructions ────────────────────────────────────────────
    log.info("  Setup complete!  All components are ready.")
    log.info("")
    log.info("  ── Endpoints ────────────────────────────────")
    log.info("    Management Console: http://localhost:8080")
    log.info("      Config editor, secrets, service control")
    log.info("")
    log.info("    LiteLLM Proxy:     http://localhost:4000")
    log.info("    LiteLLM Admin UI:  http://localhost:4000/ui")
    log.info("    Grafana:           http://localhost:3000")
    log.info("    Prometheus:        http://localhost:9090")
    log.info("")
    log.info("  ── LiteLLM Setup ────────────────────────────")
    log.info("    1. Open http://localhost:4000/ui")
    log.info("    2. Log in with the default master key:")
    log.info("         sk-gateway-master-change-me")
    log.info("    3. IMPORTANT: Change the master key!")
    log.info("       Go to Management Console → Secrets tab")
    log.info("       (http://localhost:8080)")
    log.info("       Update LITELLM_MASTER_KEY and save.")
    log.info("       LiteLLM will be restarted automatically.")
    log.info("    4. Create virtual API keys for your agents")
    log.info("       (Claude Code, Cursor) in the LiteLLM UI.")
    log.info("=" * 52)
    return 0


if __name__ == "__main__":
    sys.exit(main())
