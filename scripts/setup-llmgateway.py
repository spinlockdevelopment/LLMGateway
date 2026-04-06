#!/usr/bin/env python3
"""
LLM Gateway — Setup Script
============================
Provisions all components for the LLM Gateway stack on macOS (Apple Silicon).
Safe to run repeatedly — every step is idempotent.

Self-bootstrapping: if not running in the project venv, creates it and
re-launches itself. No separate bootstrap script required.

Prerequisites (install these first):
  - Python 3.11+
  - Docker Desktop
  - Git

Flow:
  Phase 0 — Self-bootstrap (venv creation if needed)
  Phase 1 — Sanity checks (Python, Docker)
  Phase 2 — Configuration (data dir, optional components)
  Phase 3 — Provisioning (Docker stack, DMR, optional components)
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


# ── Phase 0: Self-bootstrap ──────────────────────────────────────────────────

def _in_venv() -> bool:
    """Return True if running inside a virtual environment."""
    return sys.prefix != sys.base_prefix


def _bootstrap_venv() -> None:
    """
    If not running inside the project venv, create it (if needed),
    install dependencies, and re-exec with the venv Python.
    """
    if _in_venv():
        return

    # console.py has zero external deps — safe to import from system Python
    sys.path.insert(0, str(_SCRIPT_DIR))
    from console import info, success, error, dim, banner, blank

    banner("Phase 0 — Environment Setup")
    blank()

    # Check prerequisites
    _check_prerequisites()

    venv_dir = _REPO_DIR / ".venv"
    venv_python = venv_dir / "bin" / "python3"

    # Create venv if it doesn't exist
    if not venv_python.exists():
        info(f"  Creating virtual environment...")
        try:
            subprocess.run(
                [sys.executable, "-m", "venv", str(venv_dir)],
                check=True,
            )
        except subprocess.CalledProcessError:
            error(f"Failed to create virtual environment at {venv_dir}")
            info("  Try: python3 -m venv .venv")
            sys.exit(1)
        # Ensure scripts are executable
        for script in venv_dir.glob("bin/*"):
            try:
                script.chmod(script.stat().st_mode | 0o111)
            except OSError:
                pass
        success(f"Virtual environment: {dim(str(venv_dir))}")
    else:
        success(f"Virtual environment: {dim('already exists')}")

    # Install/upgrade dependencies
    requirements = _REPO_DIR / "requirements.txt"
    if requirements.exists():
        info(f"  Installing dependencies...")
        try:
            subprocess.run(
                [str(venv_python), "-m", "pip", "install", "--quiet",
                 "--upgrade", "pip"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                [str(venv_python), "-m", "pip", "install", "--quiet",
                 "-r", str(requirements)],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            error(f"Failed to install dependencies: {e}")
            info("  Try: .venv/bin/pip install -r requirements.txt")
            sys.exit(1)
        success(f"Dependencies: {dim('installed')}")

    # Re-exec with venv Python — use the symlink path, NOT .resolve(),
    # so Python's startup detects pyvenv.cfg and activates the venv.
    venv_bin = str(venv_python)
    blank()
    info(f"  {dim('Entering virtual environment...')}")
    sys.stdout.flush()
    try:
        os.execv(venv_bin, [venv_bin] + sys.argv)
    except OSError as e:
        error(f"Cannot exec venv Python ({venv_bin}): {e}")
        info("  Try: rm -rf .venv && python3 scripts/setup-llmgateway.py")
        sys.exit(1)


def _check_prerequisites() -> None:
    """Verify Python version and Docker are available."""
    from console import success, error, info, dim

    # Python version
    if sys.version_info < (3, 11):
        error(f"Python 3.11+ required (found {sys.version.split()[0]})")
        info("  Install: brew install python@3.12")
        sys.exit(1)
    success(f"Python: {dim(sys.version.split()[0])}")

    # Docker
    if not shutil.which("docker"):
        error("Docker Desktop not found.")
        info("  Install: https://docker.com/products/docker-desktop/")
        sys.exit(1)
    success(f"Docker: {dim('found')}")


# ── From here on, we're in the venv ──────────────────────────────────────────

def _main_in_venv() -> int:
    """Main entry point, running inside the project venv."""
    sys.path.insert(0, str(_SCRIPT_DIR))

    from console import (
        info, success, warn, error, bold, dim, green, red, yellow, cyan,
        heading, separator, blank, banner,
        is_interactive, prompt_yes_no, prompt_input,
    )
    from data_dir import get_data_dir, ensure_data_dir, env_path, load_install_config

    # ── Logging (debug + syslog only; user-facing output uses console) ──

    def _setup_logging(verbose: bool = False) -> logging.Logger:
        logger = logging.getLogger("llm-gateway-provision")
        logger.setLevel(logging.DEBUG if verbose else logging.WARNING)
        if verbose:
            console = logging.StreamHandler()
            console.setLevel(logging.DEBUG)
            console.setFormatter(logging.Formatter("  [debug] %(message)s"))
            logger.addHandler(console)
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

    # ── Helpers ──────────────────────────────────────────────────────────

    def _is_root() -> bool:
        try:
            return os.geteuid() == 0
        except AttributeError:
            return False

    def _install_brew_formula(formula: str, binary_name: str = "") -> bool:
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

    def _install_management_console(data_dir: Path) -> bool:
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

    # ── Configuration ────────────────────────────────────────────────────

    def _collect_data_dir(existing: dict) -> str:
        default = existing.get("data_dir", "~/.llm-gateway")
        info(f"  Gateway data (secrets, config, logs) is stored separately")
        info(f"  from the git repo so it survives repo deletion/re-clone.")
        blank()
        return prompt_input("Data directory", default)

    def _collect_components(existing: dict) -> dict:
        """Toggle menu for optional components. Returns dict of choices."""
        observability = existing.get("install_observability", False)
        whisper = existing.get("install_whisper", False)
        llmfit = existing.get("install_llmfit", False)

        if not is_interactive():
            return {
                "install_observability": observability,
                "install_whisper": whisper,
                "install_llmfit": llmfit,
            }

        blank()
        info("  Optional components (toggle numbers, then 4 to continue):")
        while True:
            def mark(on: bool) -> str:
                return green("[x]") if on else dim("[ ]")

            blank()
            info(f"    1) Observability (Grafana, Prometheus, Loki)  {mark(observability)}  ~400MB RAM")
            info(f"    2) Whisper (speech-to-text server)            {mark(whisper)}  ~150MB disk")
            info(f"    3) llmfit (hardware model recommendations)    {mark(llmfit)}  ~50MB disk")
            info(f"    4) Continue")
            try:
                raw = input("  Choice (1-4): ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if raw == "1":
                observability = not observability
            elif raw == "2":
                whisper = not whisper
            elif raw == "3":
                llmfit = not llmfit
            elif raw == "4":
                break

        return {
            "install_observability": observability,
            "install_whisper": whisper,
            "install_llmfit": llmfit,
        }

    def _save_install_config(data_dir: Path, install_config: dict) -> None:
        """Save install choices to the install: section of llmgateway.yaml."""
        import yaml
        config_path = data_dir / "config" / "llmgateway.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)

        existing = {}
        if config_path.exists():
            try:
                existing = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            except Exception:
                pass

        existing["install"] = install_config
        config_path.write_text(
            yaml.dump(existing, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
        try:
            os.chmod(config_path, 0o600)
        except OSError:
            pass

    def _generate_env_file(env_example: Path, env_output: Path) -> None:
        """Copy .env.example to .env if it doesn't exist yet."""
        if env_output.exists():
            info(f"  {dim('.env already exists — keeping current values')}")
            return
        if not env_example.exists():
            warn(".env.example not found — create .env manually")
            return
        env_output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(env_example, env_output)
        success(f".env created from template: {env_output}")

    def _collect_configuration() -> tuple[Path, dict]:
        banner("Phase 2 — Configuration")

        # Load existing config if data dir already exists
        existing = load_install_config(get_data_dir())

        # Data directory
        heading("Data Directory")
        data_dir_str = _collect_data_dir(existing)
        blank()

        os.environ["LLM_GATEWAY_DATA_DIR"] = str(
            Path(data_dir_str).expanduser().resolve()
        )
        data_dir = ensure_data_dir()
        success(f"Data directory: {data_dir}")

        # Reload config from the confirmed data dir
        existing = load_install_config(data_dir)
        existing["data_dir"] = data_dir_str

        # Components
        heading("Optional Components")
        components = _collect_components(existing)
        existing.update(components)

        selected = [k.replace("install_", "") for k, v in components.items() if v]
        if selected:
            success(f"Selected: {', '.join(selected)}")
        else:
            info(f"  {dim('No optional components selected')}")

        # Save
        blank()
        separator(56)
        info("  Writing configuration...")
        _save_install_config(data_dir, existing)
        success(f"Config: {data_dir / 'config' / 'llmgateway.yaml'}")

        _generate_env_file(_REPO_DIR / ".env.example", env_path())
        success(f"Secrets: {env_path()}")

        return data_dir, existing

    def _migrate_old_env() -> None:
        """If .env exists in the repo root (old layout), offer to migrate."""
        old_env = _REPO_DIR / ".env"
        new_env = env_path()
        if not old_env.exists() or new_env.exists():
            return
        info(f"  Found .env in repo root (old layout): {old_env}")
        if prompt_yes_no("  Migrate to data directory?"):
            shutil.copy2(old_env, new_env)
            old_env.rename(old_env.with_suffix(".migrated"))
            success(f"Migrated .env -> {new_env}")

    # ── Main flow ────────────────────────────────────────────────────────

    parser = argparse.ArgumentParser(
        description="LLM Gateway setup — provisions stack components on macOS.",
    )
    parser.add_argument("--status", action="store_true", help="Status check only.")
    parser.add_argument("--verbose", action="store_true", help="Debug-level output.")
    args = parser.parse_args()

    log = _setup_logging(verbose=args.verbose)
    dry_run = args.status

    if _is_root() and not dry_run:
        blank()
        warn("Running as root — this script does not require elevated privileges.")
        if not prompt_yes_no("  Continue as root anyway?", default=False):
            info("  Re-run without sudo: python3 scripts/setup-llmgateway.py")
            return 1
        blank()

    # ── Phase 1: Sanity Checks ────────────────────────────────────────
    banner("Phase 1 — Sanity Checks")
    blank()
    info(f"  Python:       {sys.version.split()[0]}")
    info(f"  Platform:     {platform.platform()}")
    info(f"  Architecture: {platform.machine()}")
    info(f"  Repo:         {_REPO_DIR}")
    if dry_run:
        info(f"  Mode:         {yellow('status check (no changes)')}")
    blank()

    # ── Phase 2: Configuration ────────────────────────────────────────
    if not dry_run:
        _migrate_old_env()
        data_dir, install_cfg = _collect_configuration()
    else:
        data_dir = get_data_dir()
        install_cfg = load_install_config(data_dir)
        info(f"  Data dir:     {data_dir}")
        blank()

    observability = install_cfg.get("install_observability", False)

    # ── Phase 3: Provisioning ─────────────────────────────────────────
    banner("Phase 3 — Provisioning")
    blank()

    from steps.docker import setup as docker_setup
    from steps.env_file import setup as env_setup
    from steps.docker_stack import setup as stack_setup
    from steps.dmr import setup as dmr_setup
    from steps.llmfit_setup import setup as llmfit_setup

    failures: list[str] = []

    # Core steps
    for name, fn in [
        ("Docker Desktop", lambda: docker_setup(dry_run=dry_run)),
        ("Environment File", lambda: env_setup(_REPO_DIR, data_dir, dry_run=dry_run)),
        ("Docker Stack", lambda: stack_setup(_REPO_DIR, data_dir, observability, dry_run=dry_run)),
    ]:
        ok = fn()
        blank()
        if not ok:
            failures.append(name)

    # Optional steps
    if not dry_run:
        heading("Optional Components")
        blank()

        # DMR — always run (ships with Docker Desktop)
        ok = dmr_setup(dry_run=False)
        blank()
        if not ok:
            failures.append("Docker Model Runner")

        # llmfit — conditional
        if install_cfg.get("install_llmfit", False):
            ok = llmfit_setup(dry_run=False)
            blank()
            if not ok:
                failures.append("llmfit")
        else:
            info(f"  {dim('llmfit: not selected  (enable later: re-run setup)')}")
            blank()

        # Whisper — conditional
        if install_cfg.get("install_whisper", False):
            info("  Checking whisper-server...")
            if not _install_brew_formula("whisper-cpp", binary_name="whisper-server"):
                failures.append("whisper-server")
            blank()
        else:
            info(f"  {dim('whisper-server: not selected  (install later: brew install whisper-cpp)')}")
            blank()

    else:
        dmr_setup(dry_run=True)
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

    # ── Phase 4: Summary ──────────────────────────────────────────────
    banner("Phase 4 — Summary")
    blank()

    if dry_run:
        success("Status check complete.")
        return 0

    if failures:
        error("Setup completed with failures:")
        for name in failures:
            info(f"    {red('x')} {name}")
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
    if observability:
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
    info(f"    2. Add API keys in the Secrets tab")
    info(f"    3. Run {bold('./gw')} to check status anytime")
    blank()
    return 0


# ── Entry point ──────────────────────────────────────────────────────────────

def main() -> int:
    _bootstrap_venv()
    return _main_in_venv()


if __name__ == "__main__":
    sys.exit(main())
