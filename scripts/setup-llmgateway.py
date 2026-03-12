#!/usr/bin/env python3
"""
LLM Gateway — Setup Script
============================
Provisions all application-level components for the LLM Gateway stack on
macOS (Apple Silicon). Safe to run on every boot — every step is idempotent.

This script does NOT require admin/root privileges (except optional SSH).

Flow:
  Phase 1 — Sanity checks (Python, Docker, Homebrew, Git)
  Phase 2 — Upfront configuration collection
             (data dir, components, SSH, secrets)
  Phase 3 — Provisioning (conditional on selections)
  Phase 4 — Summary

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

from console import (
    info, success, warn, error, bold, dim, green, red, yellow, cyan,
    heading, separator, blank, banner,
    is_interactive, prompt_yes_no, prompt_input, prompt_secret,
)
from data_dir import get_data_dir, ensure_data_dir, setup_config_path, env_path
from setup_config import SetupConfig


# ── Logging (provisioning steps use logging internally) ──────────────────────
# Custom handler strips timestamps for console output while steps
# continue to use the standard logging API.

class _CleanConsoleHandler(logging.Handler):
    """Log handler that prints without timestamps — just the message."""
    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        if record.levelno >= logging.ERROR:
            error(msg.lstrip())
        elif record.levelno >= logging.WARNING:
            warn(msg.lstrip())
        else:
            info(f"  {msg.lstrip()}")


def _setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure logging for provisioning steps."""
    logger = logging.getLogger("llm-gateway-provision")
    logger.setLevel(logging.DEBUG)

    console = _CleanConsoleHandler()
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    console.setFormatter(logging.Formatter("%(message)s"))
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
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False


def _install_brew_formula(formula: str, binary_name: str = "") -> bool:
    """Install a Homebrew formula if its binary is not already on PATH."""
    check_name = binary_name or formula
    if shutil.which(check_name):
        result = subprocess.run(
            [check_name, "--version"],
            capture_output=True, text=True, timeout=10,
        )
        version = result.stdout.strip() or result.stderr.strip() or "installed"
        success(f"{check_name}: {version}")
        return True

    if not shutil.which("brew"):
        warn(f"Cannot install {formula} — Homebrew not found")
        return False

    info(f"  Installing {formula} via Homebrew...")
    try:
        subprocess.run(["brew", "install", formula], check=True, timeout=600)
        success(f"{formula}: installed")
        return True
    except subprocess.CalledProcessError as e:
        error(f"Failed to install {formula}: {e}")
    except subprocess.TimeoutExpired:
        error(f"Timed out installing {formula}")
    return False


def _start_ollama_if_installed() -> None:
    """Start the Ollama server if installed and not already running."""
    if not shutil.which("ollama"):
        return
    try:
        result = subprocess.run(
            ["curl", "-sf", "http://localhost:11434/api/tags"],
            capture_output=True, timeout=5,
        )
        if result.returncode == 0:
            success("Ollama server already running")
            return
    except Exception:
        pass
    if shutil.which("brew"):
        list_result = subprocess.run(
            ["brew", "services", "list"],
            capture_output=True, text=True, timeout=15,
        )
        if list_result.returncode == 0 and "ollama" in (list_result.stdout or ""):
            info("  Starting Ollama via brew services...")
            subprocess.run(
                ["brew", "services", "start", "ollama"],
                capture_output=True, timeout=30,
            )
            time.sleep(2)
            return
    info("  Starting Ollama server in background...")
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        time.sleep(2)
    except Exception:
        pass


def _install_management_console(data_dir: Path) -> bool:
    """Register the management console as a launchd agent and start it."""
    try:
        from launchd.manager import install as launchd_install, is_loaded
        from config.manager import ConfigManager

        config_dir = _REPO_DIR / "config"
        user_config_dir = data_dir / "config"
        cm = ConfigManager(config_dir, user_config_dir=user_config_dir)
        cm.load()
        port = cm.config.get("gateway", {}).get("port", 8080)

        info(f"  Registering management console on port {port}...")
        ok = launchd_install(repo_dir=_REPO_DIR, port=port, data_dir=data_dir)
        if not ok:
            error("Failed to install launchd agent")
            return False

        for attempt in range(1, 6):
            time.sleep(2)
            if not is_loaded():
                continue
            try:
                result = subprocess.run(
                    ["curl", "-sf", f"http://localhost:{port}/api/status"],
                    capture_output=True, text=True, timeout=10,
                )
                if result.returncode == 0:
                    success(f"Management console: running at http://localhost:{port}")
                    return True
            except Exception:
                pass
        success("Management console: installed (may still be starting)")
        info(f"  Dashboard: http://localhost:{port}")
        return True

    except Exception as e:
        error(f"Management console setup failed: {e}")
        return False


# ── Virtual environment check ─────────────────────────────────────────────────

def _ensure_venv() -> None:
    """Re-exec inside the project venv if we're not already there."""
    venv_dir = _REPO_DIR / ".venv"
    venv_python = venv_dir / "bin" / "python3"

    if venv_python.exists():
        try:
            if Path(sys.executable).samefile(venv_python):
                return
        except OSError:
            pass

    try:
        current_exe = Path(sys.executable).resolve()
        current_exe.relative_to(venv_dir.resolve())
        return
    except (ValueError, OSError):
        pass

    if venv_python.exists():
        resolved = str(venv_python.resolve())
        info(f"  Re-launching with venv Python: {resolved}")
        try:
            os.execv(resolved, [resolved] + sys.argv)
        except OSError as e:
            error(f"Cannot exec venv Python ({resolved}): {e}")
            sys.exit(1)

    error("Project virtual environment not found.")
    info(f"  Expected: {venv_dir}")
    info(f"  Run: ./bootstrap-llmgateway.sh")
    sys.exit(1)


# ── Phase 2: Configuration Collection ────────────────────────────────────────

def _collect_data_dir(existing: SetupConfig) -> str:
    """Ask where to store gateway data."""
    default = existing.data_dir or "~/.llm-gateway"
    info(f"  Gateway data (secrets, config, logs) is stored separately")
    info(f"  from the git repo so it survives repo deletion/re-clone.")
    blank()
    return prompt_input("Data directory", default)


def _collect_components(existing: SetupConfig) -> tuple[bool, bool, bool]:
    """Toggle menu for optional local components."""
    ollama = existing.install_ollama
    llama = existing.install_llama_cpp
    whisper = existing.install_whisper

    if not is_interactive():
        return (ollama, llama, whisper)

    blank()
    info("  Select optional local components (toggle numbers, then 4 to proceed):")
    while True:
        def mark(on: bool) -> str:
            return green("[x]") if on else dim("[ ]")

        fourth = "Continue" if (ollama or llama or whisper) else "Skip"
        blank()
        info(f"    1) Ollama (local LLM, Metal GPU)        {mark(ollama)}")
        info(f"    2) llama-server (llama.cpp, GGUF)       {mark(llama)}")
        info(f"    3) whisper-server (speech-to-text)      {mark(whisper)}")
        info(f"    4) {fourth}")
        try:
            raw = input("  Choice (1-4): ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if raw == "1":
            ollama = not ollama
        elif raw == "2":
            llama = not llama
        elif raw == "3":
            whisper = not whisper
        elif raw == "4":
            break

    return (ollama, llama, whisper)


def _collect_ssh() -> tuple[bool, str]:
    """Collect SSH remote access preferences."""
    from steps.ssh_setup import check_remote_login_status, validate_ssh_public_key

    blank()
    status = check_remote_login_status()
    if status == "on":
        info(f"  Remote Login (SSH): {green('already enabled')}")
        enable = False
    elif status == "off":
        info(f"  Remote Login (SSH): {yellow('disabled')}")
        enable = prompt_yes_no("  Enable Remote Login (SSH)? (requires sudo)", default=False)
    else:
        info(f"  Remote Login (SSH): {dim('status unknown')}")
        enable = prompt_yes_no("  Try to enable Remote Login? (requires sudo)", default=False)

    blank()
    info("  To allow SSH access from another machine, paste its public key.")
    info(f"  {dim('(On the remote machine: cat ~/.ssh/id_ed25519.pub)')}")
    key = ""
    try:
        raw = input("  Public key (or Enter to skip): ").strip()
    except (EOFError, KeyboardInterrupt):
        raw = ""
    if raw:
        if validate_ssh_public_key(raw):
            key = raw
            success("Valid SSH public key")
        else:
            warn("That doesn't look like a valid SSH public key — skipping")

    return enable, key


def _collect_secrets(existing: SetupConfig) -> SetupConfig:
    """Collect essential API keys and credentials."""
    blank()
    info("  Configure essential secrets. Press Enter to keep existing/skip.")
    info(f"  {dim('You can add more providers later via http://localhost:8080')}")
    blank()

    cfg = existing

    cfg.litellm_master_key = prompt_secret(
        "LiteLLM master key (admin API + /ui login)",
        default=cfg.litellm_master_key or "sk-gateway-master-change-me",
    )

    cfg.openrouter_api_key = prompt_secret(
        "OpenRouter API key (https://openrouter.ai/keys)",
        default=cfg.openrouter_api_key,
    )

    cfg.anthropic_api_key = prompt_secret(
        "Anthropic API key (optional fallback)",
        default=cfg.anthropic_api_key,
    )

    cfg.grafana_admin_password = prompt_secret(
        "Grafana admin password",
        default=cfg.grafana_admin_password or "llmgateway",
    )

    return cfg


def _collect_configuration() -> SetupConfig:
    """Phase 2: Collect all configuration upfront in one pass."""
    banner("Phase 2 — Configuration")

    # Load existing config if present (re-run scenario)
    cfg = SetupConfig.load(setup_config_path())

    # 2a. Data directory
    heading("Data Directory")
    cfg.data_dir = _collect_data_dir(cfg)
    blank()

    # Set env var so data_dir module picks it up for the rest of setup
    os.environ["LLM_GATEWAY_DATA_DIR"] = str(
        Path(cfg.data_dir).expanduser().resolve()
    )
    data_dir = ensure_data_dir()
    success(f"Data directory: {data_dir}")

    # 2b. Components
    heading("Optional Components")
    cfg.install_ollama, cfg.install_llama_cpp, cfg.install_whisper = (
        _collect_components(cfg)
    )
    selected = cfg.selected_components()
    if selected:
        success(f"Selected: {', '.join(selected)}")
    else:
        info(f"  {dim('No optional components selected')}")

    # 2c. SSH
    heading("SSH Remote Access")
    cfg.ssh_enable_remote_login, cfg.ssh_authorized_key = _collect_ssh()

    # 2d. Secrets
    heading("API Keys & Secrets")
    cfg = _collect_secrets(cfg)

    # 2e. Write config
    blank()
    separator(56)
    info("  Writing configuration...")

    cfg.save(setup_config_path())
    success(f"Setup config: {setup_config_path()}")

    env_example = _REPO_DIR / ".env.example"
    env_output = env_path()
    if env_output.exists():
        info(f"  {dim('.env already exists — updating with any new values')}")
    cfg.generate_env_file(env_example, env_output)
    success(f"Secrets: {env_output}")

    return cfg


def _migrate_old_env() -> None:
    """If .env exists in the repo root (old layout), offer to migrate."""
    old_env = _REPO_DIR / ".env"
    new_env = env_path()

    if not old_env.exists():
        return
    if new_env.exists():
        return

    info(f"  Found .env in repo root (old layout): {old_env}")
    if prompt_yes_no("  Migrate to data directory?"):
        shutil.copy2(old_env, new_env)
        old_env.rename(old_env.with_suffix(".migrated"))
        success(f"Migrated .env → {new_env}")
    else:
        info(f"  {dim('Skipping migration')}")

    old_config = _REPO_DIR / "config" / "llmgateway.yaml"
    new_config = get_data_dir() / "config" / "llmgateway.yaml"
    if old_config.exists() and not new_config.exists():
        new_config.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(old_config, new_config)
        success(f"Migrated config → {new_config}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    _ensure_venv()

    parser = argparse.ArgumentParser(
        description="LLM Gateway setup — provisions stack components on macOS.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--status", action="store_true", help="Status check only.")
    parser.add_argument("--verbose", action="store_true", help="Debug-level output.")
    args = parser.parse_args()

    log = _setup_logging(verbose=args.verbose)
    dry_run = args.status

    # ── Admin/root check ──────────────────────────────────────────────────
    if _is_root() and not dry_run:
        blank()
        warn("Running as root/admin — this script does not require elevated privileges.")
        warn("Running as root can cause file ownership issues.")
        if not prompt_yes_no("  Continue as root anyway?", default=False):
            info("  Re-run without sudo: python3 scripts/setup-llmgateway.py")
            return 1
        blank()

    # ── Phase 1: Sanity Checks ────────────────────────────────────────────
    banner("Phase 1 — Sanity Checks")
    blank()
    info(f"  Python:       {sys.version.split()[0]}")
    info(f"  Platform:     {platform.platform()}")
    info(f"  Architecture: {platform.machine()}")
    info(f"  Repo:         {_REPO_DIR}")
    if dry_run:
        info(f"  Mode:         {yellow('status check (no changes)')}")
    blank()

    # ── Phase 2: Configuration ────────────────────────────────────────────
    if not dry_run:
        _migrate_old_env()
        setup_cfg = _collect_configuration()
        data_dir = get_data_dir()
    else:
        data_dir = get_data_dir()
        setup_cfg = SetupConfig.load(setup_config_path())
        info(f"  Data dir:     {data_dir}")
        blank()

    # ── Phase 3: Provisioning ─────────────────────────────────────────────
    banner("Phase 3 — Provisioning")
    blank()

    try:
        from steps.git_repo import GitRepo
        from steps.nodejs import NodeJS
        from steps.claude_code import ClaudeCode
        from steps.docker import DockerDesktop
        from steps.docker_stack import DockerStack
        from steps.ollama import Ollama
        from steps.ssh_setup import SSHSetup
        from steps.env_file import EnvFile
    except ImportError as e:
        error(f"Failed to import provisioning steps: {e}")
        return 1

    core_steps = [
        GitRepo(repo_dir=_REPO_DIR),
        NodeJS(),
        ClaudeCode(),
        DockerDesktop(),
        EnvFile(repo_dir=_REPO_DIR, data_dir=data_dir),
        DockerStack(repo_dir=_REPO_DIR, data_dir=data_dir),
    ]

    failures: list[str] = []
    for step in core_steps:
        ok = step.provision(dry_run=dry_run)
        blank()
        if not ok:
            failures.append(step.name)

    # Optional steps (conditional on selections)
    if not dry_run:
        heading("Optional Components")
        blank()

        if setup_cfg.install_ollama:
            ok = Ollama().provision(dry_run=False)
            blank()
            if not ok:
                failures.append("Ollama")
            else:
                _start_ollama_if_installed()
        else:
            info(f"  {dim('Ollama: not selected  (install later: brew install ollama)')}")
            blank()

        if setup_cfg.install_llama_cpp:
            info("  Checking llama-server...")
            if not _install_brew_formula("llama.cpp", binary_name="llama-server"):
                failures.append("llama-server")
            blank()
        else:
            info(f"  {dim('llama-server: not selected  (install later: brew install llama.cpp)')}")
            blank()

        if setup_cfg.install_whisper:
            info("  Checking whisper-server...")
            if not _install_brew_formula("whisper-cpp", binary_name="whisper-server"):
                failures.append("whisper-server")
            blank()
        else:
            info(f"  {dim('whisper-server: not selected  (install later: brew install whisper-cpp)')}")
            blank()

        # SSH
        if setup_cfg.ssh_enable_remote_login or setup_cfg.ssh_authorized_key:
            ssh_step = SSHSetup(
                enable_login=setup_cfg.ssh_enable_remote_login,
                authorized_key=setup_cfg.ssh_authorized_key,
            )
            ok = ssh_step.provision(dry_run=False)
            blank()
            if not ok:
                failures.append("SSH")
        else:
            info(f"  {dim('SSH: not configured')}")
            blank()

    else:
        optional_status_steps = [Ollama()]
        for step in optional_status_steps:
            step.provision(dry_run=True)
            blank()

    # Management Console
    if not dry_run:
        heading("Management Console")
        blank()
        info("  The management console provides a web dashboard for")
        info("  config editing, secrets management, and service control.")
        blank()
        if not _install_management_console(data_dir):
            failures.append("Management Console")
        blank()

    # ── Phase 4: Summary ──────────────────────────────────────────────────
    banner("Phase 4 — Summary")
    blank()

    if dry_run:
        success("Status check complete.")
        return 0

    if failures:
        error("Setup completed with failures:")
        for name in failures:
            info(f"    {red('✗')} {name}")
        blank()
        info("  Fix the issues above and re-run:")
        info("    python3 scripts/setup-llmgateway.py")
        return 1

    success("Setup complete! All components are ready.")
    blank()
    info(f"  {bold('Endpoints')}")
    separator(50)
    info(f"    Management Console: {cyan('http://localhost:8080')}")
    info(f"      Config editor, secrets, service control")
    blank()
    info(f"    LiteLLM Proxy:     {cyan('http://localhost:4000')}")
    info(f"    LiteLLM Admin UI:  {cyan('http://localhost:4000/ui')}")
    info(f"    Grafana:           {cyan('http://localhost:3000')}")
    info(f"    Prometheus:        {cyan('http://localhost:9090')}")
    blank()
    info(f"  {bold('Data Directory')}")
    separator(50)
    info(f"    {data_dir}")
    blank()
    info(f"  {bold('Next Steps')}")
    separator(50)
    info(f"    1. Visit {cyan('http://localhost:8080')} to manage configuration")
    info(f"    2. Add more API keys in the Secrets tab")
    info(f"    3. Run {bold('./gw')} to check status anytime")
    blank()
    return 0


if __name__ == "__main__":
    sys.exit(main())
