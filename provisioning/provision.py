#!/usr/bin/env python3
"""
LLM Gateway — Provisioning Script
==================================
Ensures all dependencies are installed and configured for the
LLM Gateway stack on macOS (Apple Silicon).

Safe to run on every boot. Every step is idempotent.

Components provisioned:
  - Node.js + npm (via Homebrew)
  - Claude Code CLI (via npm)
  - Docker Desktop + Docker Compose
  - Ollama (bare metal for Metal GPU)
  - SSH server (macOS Remote Login)
  - Docker Compose stack (optional --launch)

Usage:
  python3 provisioning/provision.py
  python3 provisioning/provision.py --launch
  python3 provisioning/provision.py --launch --repo-dir ~/src/LLMGateway
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

# ── Logging Setup ────────────────────────────────────────────

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(log_file: str, verbose: bool = False) -> logging.Logger:
    """Configure logging to file + syslog + optionally stdout."""
    logger = logging.getLogger("llm-gateway-provision")
    logger.setLevel(logging.DEBUG)

    # File handler
    fh = logging.FileHandler(log_file, mode="a")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    logger.addHandler(fh)

    # Stdout handler
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.DEBUG if verbose else logging.INFO)
    sh.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    logger.addHandler(sh)

    # macOS syslog handler (best-effort)
    try:
        from logging.handlers import SysLogHandler
        syslog = SysLogHandler(address="/var/run/syslog")
        syslog.setLevel(logging.INFO)
        syslog.setFormatter(logging.Formatter(
            "llm-gateway-provision: [%(levelname)s] %(message)s"
        ))
        logger.addHandler(syslog)
    except Exception:
        pass  # syslog not available

    return logger


# ── Utility Functions ────────────────────────────────────────

def run(
    cmd: list[str] | str,
    check: bool = True,
    capture: bool = True,
    shell: bool = False,
    timeout: int = 300,
) -> subprocess.CompletedProcess:
    """Run a command, log it, return result."""
    cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
    log.debug(f"Running: {cmd_str}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            check=check,
            shell=shell,
            timeout=timeout,
        )
        if result.stdout and result.stdout.strip():
            log.debug(f"stdout: {result.stdout.strip()[:500]}")
        if result.stderr and result.stderr.strip():
            log.debug(f"stderr: {result.stderr.strip()[:500]}")
        return result
    except subprocess.CalledProcessError as e:
        log.error(f"Command failed (exit {e.returncode}): {cmd_str}")
        if e.stdout:
            log.error(f"stdout: {e.stdout.strip()[:500]}")
        if e.stderr:
            log.error(f"stderr: {e.stderr.strip()[:500]}")
        raise
    except subprocess.TimeoutExpired:
        log.error(f"Command timed out after {timeout}s: {cmd_str}")
        raise


def command_exists(cmd: str) -> bool:
    """Check if a command is available on PATH."""
    return shutil.which(cmd) is not None


def get_version(cmd: str, flag: str = "--version") -> Optional[str]:
    """Get version string from a command."""
    try:
        result = run([cmd, flag], check=False, capture=True)
        return result.stdout.strip() or result.stderr.strip()
    except Exception:
        return None


def brew_install(package: str, cask: bool = False) -> bool:
    """Install a package via Homebrew if not already installed."""
    check_cmd = ["brew", "list", "--cask", package] if cask else ["brew", "list", package]
    result = run(check_cmd, check=False)
    if result.returncode == 0:
        log.info(f"  {package}: already installed via Homebrew")
        return False

    install_cmd = ["brew", "install"]
    if cask:
        install_cmd.append("--cask")
    install_cmd.append(package)
    log.info(f"  Installing {package} via Homebrew...")
    run(install_cmd, timeout=600)
    log.info(f"  {package}: installed")
    return True


# ── Provisioning Steps ──────────────────────────────────────

def provision_nodejs() -> None:
    """Ensure Node.js and npm are installed and updated."""
    log.info("── Node.js + npm ──────────────────────────")

    if command_exists("node"):
        version = get_version("node")
        log.info(f"  Node.js: {version}")

        # Check minimum version (need 18+)
        try:
            major = int(version.replace("v", "").split(".")[0])
            if major < 18:
                log.info(f"  Node.js {major} is too old (need 18+). Upgrading...")
                run(["brew", "upgrade", "node"], check=False)
        except (ValueError, IndexError):
            pass
    else:
        brew_install("node")

    # Update npm
    log.info("  Updating npm to latest...")
    run(["npm", "install", "-g", "npm@latest"], check=False, timeout=120)
    npm_version = get_version("npm")
    log.info(f"  npm: {npm_version}")


def provision_claude_code() -> None:
    """Install or update Claude Code CLI via npm."""
    log.info("── Claude Code CLI ────────────────────────")

    # Check if already installed
    result = run(["npm", "list", "-g", "@anthropic-ai/claude-code"], check=False)
    if result.returncode == 0 and "@anthropic-ai/claude-code" in result.stdout:
        log.info("  Claude Code: already installed globally")
        log.info("  Checking for updates...")
        run(["npm", "update", "-g", "@anthropic-ai/claude-code"], check=False, timeout=120)
    else:
        log.info("  Installing Claude Code CLI...")
        run(["npm", "install", "-g", "@anthropic-ai/claude-code"], timeout=180)
        log.info("  Claude Code: installed")

    # Verify
    if command_exists("claude"):
        version = get_version("claude")
        log.info(f"  Claude Code CLI: {version}")
    else:
        log.warn("  'claude' command not found on PATH after install")


def provision_docker() -> None:
    """Ensure Docker Desktop and Docker Compose are installed."""
    log.info("── Docker Desktop + Compose ────────────────")

    if command_exists("docker"):
        version = get_version("docker")
        log.info(f"  Docker: {version}")
    else:
        log.info("  Docker not found. Installing Docker Desktop...")
        brew_install("docker", cask=True)

        # Wait for Docker Desktop to be ready
        log.info("  Waiting for Docker Desktop to start...")
        log.info("  (You may need to open Docker Desktop and accept the license)")
        for attempt in range(30):
            result = run(["docker", "info"], check=False, capture=True)
            if result.returncode == 0:
                log.info("  Docker Desktop is running")
                break
            time.sleep(5)
            if attempt % 6 == 5:
                log.info(f"  Still waiting for Docker ({(attempt + 1) * 5}s)...")
        else:
            log.warning("  Docker Desktop did not start within 150s.")
            log.warning("  Please start Docker Desktop manually and re-run.")

    # Docker Compose (included with Docker Desktop on macOS)
    compose_result = run(["docker", "compose", "version"], check=False)
    if compose_result.returncode == 0:
        log.info(f"  Docker Compose: {compose_result.stdout.strip()}")
    else:
        log.warning("  Docker Compose not found. It should be included with Docker Desktop.")
        log.warning("  Try restarting Docker Desktop or install via: brew install docker-compose")


def provision_ollama() -> None:
    """Ensure Ollama is installed (bare metal for Metal GPU acceleration)."""
    log.info("── Ollama (bare metal) ────────────────────")

    if command_exists("ollama"):
        version = get_version("ollama")
        log.info(f"  Ollama: {version}")

        # Check if Ollama server is running
        result = run(["curl", "-sf", "http://localhost:11434/api/tags"], check=False)
        if result.returncode == 0:
            log.info("  Ollama server: running")
            try:
                data = json.loads(result.stdout)
                models = [m.get("name", "?") for m in data.get("models", [])]
                if models:
                    log.info(f"  Loaded models: {', '.join(models[:10])}")
                else:
                    log.info("  No models loaded yet. Pull one with: ollama pull llama3.2:3b")
            except (json.JSONDecodeError, KeyError):
                pass
        else:
            log.info("  Ollama server: not running")
            log.info("  Start with: ollama serve")
    else:
        brew_install("ollama")
        log.info("  Start Ollama with: ollama serve")
        log.info("  Then pull a model: ollama pull llama3.2:3b")


def provision_ssh() -> None:
    """Ensure SSH is configured for remote access."""
    log.info("── SSH Configuration ──────────────────────")

    if platform.system() != "Darwin":
        log.info("  Not macOS — skipping SSH configuration")
        return

    # Check if Remote Login is enabled
    result = run(["sudo", "systemsetup", "-getremotelogin"], check=False)
    remote_login_status = result.stdout.strip().lower() if result.stdout else ""

    if "on" in remote_login_status:
        log.info("  Remote Login (SSH): enabled")
    else:
        log.info("  Remote Login (SSH): disabled")
        log.info("  To enable SSH, run:")
        log.info("    sudo systemsetup -setremotelogin on")
        log.info("  Or enable via: System Settings → General → Sharing → Remote Login")

    # Check SSH directory and keys
    ssh_dir = Path.home() / ".ssh"
    if not ssh_dir.exists():
        log.info("  Creating ~/.ssh directory...")
        ssh_dir.mkdir(mode=0o700, exist_ok=True)

    authorized_keys = ssh_dir / "authorized_keys"
    if authorized_keys.exists():
        key_count = sum(1 for line in authorized_keys.read_text().splitlines() if line.strip() and not line.startswith("#"))
        log.info(f"  Authorized keys: {key_count} key(s) configured")
    else:
        log.info("  No authorized_keys file. Create one with your public keys.")
        log.info(f"  File: {authorized_keys}")

    # Check sshd config exists
    sshd_config = Path("/etc/ssh/sshd_config")
    if sshd_config.exists():
        log.info(f"  SSH config: {sshd_config}")
    else:
        log.info("  SSH config not found at standard location")


def provision_env_file(repo_dir: Path) -> None:
    """Create .env from .env.example if it doesn't exist."""
    log.info("── Environment File ───────────────────────")

    env_file = repo_dir / ".env"
    env_example = repo_dir / ".env.example"

    if env_file.exists():
        log.info(f"  .env: exists at {env_file}")
        # Check for placeholder values
        content = env_file.read_text()
        if "your-key-here" in content or "change-me" in content:
            log.warning("  .env contains placeholder values!")
            log.warning("  Edit .env and set your OPENROUTER_API_KEY and LITELLM_MASTER_KEY")
    elif env_example.exists():
        log.info("  Creating .env from .env.example...")
        shutil.copy2(env_example, env_file)
        log.warning("  .env created — you MUST edit it with your actual API keys:")
        log.warning(f"    {env_file}")
    else:
        log.warning("  No .env or .env.example found")


def launch_docker_compose(repo_dir: Path) -> bool:
    """Bring up the Docker Compose stack and run sanity checks."""
    log.info("── Launching Docker Compose Stack ─────────")

    compose_file = repo_dir / "docker" / "docker-compose.yml"
    if not compose_file.exists():
        log.error(f"  docker-compose.yml not found at {compose_file}")
        return False

    # Check Docker is running
    result = run(["docker", "info"], check=False, capture=True)
    if result.returncode != 0:
        log.error("  Docker is not running. Start Docker Desktop first.")
        return False

    # Check .env file has been configured
    env_file = repo_dir / ".env"
    if env_file.exists():
        content = env_file.read_text()
        if "your-key-here" in content:
            log.error("  .env still has placeholder API keys. Edit .env first.")
            return False

    # Pull latest images
    log.info("  Pulling latest Docker images...")
    run(
        ["docker", "compose", "-f", str(compose_file), "pull"],
        check=False,
        timeout=600,
    )

    # Bring up the stack
    log.info("  Starting services...")
    result = run(
        ["docker", "compose", "-f", str(compose_file), "up", "-d"],
        timeout=300,
    )

    if result.returncode != 0:
        log.error("  Docker Compose failed to start")
        return False

    log.info("  Waiting for services to stabilize (30s)...")
    time.sleep(30)

    # ── Sanity Checks ────────────────────────────────────────
    return run_sanity_checks(compose_file)


def run_sanity_checks(compose_file: Path) -> bool:
    """Verify all services are healthy after Docker Compose launch."""
    log.info("── Sanity Checks ──────────────────────────")
    all_ok = True

    # Check container status
    result = run(
        ["docker", "compose", "-f", str(compose_file), "ps", "--format", "json"],
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        try:
            # docker compose ps --format json outputs one JSON object per line
            for line in result.stdout.strip().splitlines():
                container = json.loads(line)
                name = container.get("Name", container.get("name", "?"))
                state = container.get("State", container.get("state", "?"))
                health = container.get("Health", container.get("health", ""))
                status_str = f"{state}" + (f" ({health})" if health else "")
                if state.lower() not in ("running",):
                    log.error(f"  ✗ {name}: {status_str}")
                    all_ok = False
                else:
                    log.info(f"  ✓ {name}: {status_str}")
        except (json.JSONDecodeError, KeyError) as e:
            log.warning(f"  Could not parse container status: {e}")

    # Check LiteLLM health
    log.info("  Checking LiteLLM Proxy health...")
    for attempt in range(6):
        result = run(
            ["curl", "-sf", "http://localhost:4000/health/liveliness"],
            check=False,
        )
        if result.returncode == 0:
            log.info("  ✓ LiteLLM Proxy: healthy (http://localhost:4000)")
            break
        time.sleep(10)
    else:
        log.error("  ✗ LiteLLM Proxy: not responding after 60s")
        all_ok = False

    # Check LiteLLM UI
    result = run(
        ["curl", "-sf", "-o", "/dev/null", "-w", "%{http_code}", "http://localhost:4000/ui/"],
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip().startswith("2"):
        log.info("  ✓ LiteLLM Dashboard: http://localhost:4000/ui")
    else:
        log.warning("  ⚠ LiteLLM Dashboard may not be ready yet")

    # Check PostgreSQL
    result = run(
        ["docker", "exec", "llm-postgres", "pg_isready", "-U", "litellm"],
        check=False,
    )
    if result.returncode == 0:
        log.info("  ✓ PostgreSQL: ready")
    else:
        log.error("  ✗ PostgreSQL: not ready")
        all_ok = False

    # Check Grafana
    result = run(
        ["curl", "-sf", "-o", "/dev/null", "-w", "%{http_code}", "http://localhost:3000/api/health"],
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip() == "200":
        log.info("  ✓ Grafana: healthy (http://localhost:3000)")
    else:
        log.warning("  ⚠ Grafana: not responding (may still be starting)")

    # Check Prometheus
    result = run(
        ["curl", "-sf", "-o", "/dev/null", "-w", "%{http_code}", "http://localhost:9090/-/healthy"],
        check=False,
    )
    if result.returncode == 0:
        log.info("  ✓ Prometheus: healthy (http://localhost:9090)")
    else:
        log.warning("  ⚠ Prometheus: not responding")

    # Check Ollama (bare metal on host)
    result = run(
        ["curl", "-sf", "http://localhost:11434/api/tags"],
        check=False,
    )
    if result.returncode == 0:
        log.info("  ✓ Ollama: running on host (http://localhost:11434)")
    else:
        log.warning("  ⚠ Ollama: not running on host. Start with: ollama serve")

    # Summary
    if all_ok:
        log.info("  ──────────────────────────────────────")
        log.info("  All services are healthy!")
        log.info("")
        log.info("  LiteLLM Proxy:  http://localhost:4000")
        log.info("  LiteLLM UI:     http://localhost:4000/ui")
        log.info("  Grafana:        http://localhost:3000")
        log.info("  Prometheus:     http://localhost:9090")
    else:
        log.error("  ──────────────────────────────────────")
        log.error("  Some services failed health checks!")
        log.error("  Check logs with: docker compose -f docker/docker-compose.yml logs")

    return all_ok


# ── Main ─────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="LLM Gateway Provisioning — ensures all dependencies are installed"
    )
    parser.add_argument(
        "--repo-dir",
        type=Path,
        default=Path.home() / "src" / "LLMGateway",
        help="Path to LLMGateway repository (default: ~/src/LLMGateway)",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default="/tmp/llm-gateway-bootstrap.log",
        help="Log file path (default: /tmp/llm-gateway-bootstrap.log)",
    )
    parser.add_argument(
        "--launch",
        action="store_true",
        help="Also bring up Docker Compose stack after provisioning",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose (debug-level) output to terminal",
    )
    args = parser.parse_args()

    # Setup logging
    global log
    log = setup_logging(args.log_file, args.verbose)

    log.info("==========================================")
    log.info("LLM Gateway Provisioning — starting")
    log.info("==========================================")
    log.info(f"Python: {sys.version}")
    log.info(f"Platform: {platform.platform()}")
    log.info(f"Architecture: {platform.machine()}")
    log.info(f"Repo dir: {args.repo_dir}")

    errors: list[str] = []

    # ── Step 1: Node.js + npm ────────────────────────────────
    try:
        provision_nodejs()
    except Exception as e:
        log.error(f"Node.js provisioning failed: {e}")
        errors.append("nodejs")

    # ── Step 2: Claude Code CLI ──────────────────────────────
    try:
        provision_claude_code()
    except Exception as e:
        log.error(f"Claude Code provisioning failed: {e}")
        errors.append("claude-code")

    # ── Step 3: Docker Desktop ───────────────────────────────
    try:
        provision_docker()
    except Exception as e:
        log.error(f"Docker provisioning failed: {e}")
        errors.append("docker")

    # ── Step 4: Ollama ───────────────────────────────────────
    try:
        provision_ollama()
    except Exception as e:
        log.error(f"Ollama provisioning failed: {e}")
        errors.append("ollama")

    # ── Step 5: SSH ──────────────────────────────────────────
    try:
        provision_ssh()
    except Exception as e:
        log.error(f"SSH provisioning failed: {e}")
        errors.append("ssh")

    # ── Step 6: Environment file ─────────────────────────────
    try:
        provision_env_file(args.repo_dir)
    except Exception as e:
        log.error(f".env provisioning failed: {e}")
        errors.append("env")

    # ── Step 7: Launch (optional) ────────────────────────────
    if args.launch:
        if "docker" in errors:
            log.error("Skipping launch — Docker provisioning failed")
        else:
            try:
                success = launch_docker_compose(args.repo_dir)
                if not success:
                    errors.append("launch")
            except Exception as e:
                log.error(f"Docker Compose launch failed: {e}")
                errors.append("launch")
    else:
        log.info("── Skipping Docker Compose Launch ─────────")
        log.info("  Run with --launch to bring up the stack")
        log.info("  Or manually: docker compose -f docker/docker-compose.yml up -d")

    # ── Summary ──────────────────────────────────────────────
    log.info("")
    log.info("==========================================")
    if errors:
        log.error(f"Provisioning completed with errors in: {', '.join(errors)}")
        log.error("Fix the issues above and re-run this script.")
        return 1
    else:
        log.info("Provisioning completed successfully!")
        log.info("")
        log.info("Next steps:")
        log.info("  1. Edit .env with your API keys (at minimum OPENROUTER_API_KEY)")
        log.info("  2. Start Ollama: ollama serve")
        log.info("  3. Pull a local model: ollama pull llama3.2:3b")
        log.info("  4. Launch the stack: bootstrap.sh --launch")
        log.info("     Or: docker compose -f docker/docker-compose.yml up -d")
        log.info("")
        log.info("  LiteLLM Proxy will be at: http://localhost:4000")
        log.info("  LiteLLM Dashboard:        http://localhost:4000/ui")
        log.info("  Grafana:                  http://localhost:3000")
        log.info("==========================================")
        return 0


if __name__ == "__main__":
    sys.exit(main())
