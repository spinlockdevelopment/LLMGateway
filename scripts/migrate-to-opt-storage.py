#!/usr/bin/env python3
"""
One-shot migration: relocate LLM Gateway state from ~/.llm-gateway/ and
Docker named volumes to /opt/storage/llmgateway/.

After running, a full macOS wipe is recoverable: re-clone the repo, run
setup, and every piece of state (secrets, config, virtual-key DB, Open
WebUI chats, dashboards, HF model cache, mlx_audio venv) is re-attached
from /opt/storage/llmgateway/.

The script is idempotent: each step checks state before acting and uses
rsync/cp-style copies (no destructive moves). Originals stay in place
until you delete them manually at the very end.

Run with:
    .venv/bin/python3 scripts/migrate-to-opt-storage.py            # do it
    .venv/bin/python3 scripts/migrate-to-opt-storage.py --dry-run  # show only
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

OLD_DATA = Path.home() / ".llm-gateway"
NEW_DATA = Path("/opt/storage/llmgateway")
OLD_HF = Path.home() / ".cache" / "huggingface"
NEW_HF = NEW_DATA / "hf-cache"
REPO_DIR = Path(__file__).resolve().parent.parent

VOLUME_MAP = {
    "docker_postgres-data":   NEW_DATA / "docker-volumes" / "postgres",
    "docker_open-webui-data": NEW_DATA / "docker-volumes" / "open-webui",
    "docker_grafana-data":    NEW_DATA / "docker-volumes" / "grafana",
    "docker_prometheus-data": NEW_DATA / "docker-volumes" / "prometheus",
    "docker_loki-data":       NEW_DATA / "docker-volumes" / "loki",
}

PLIST = Path.home() / "Library" / "LaunchAgents" / "com.local.llm-gateway.plist"
COMPOSE = REPO_DIR / "docker" / "docker-compose.yml"


def banner(msg: str) -> None:
    print(f"\n=== {msg} ===")


def run(cmd: list[str], dry: bool, check: bool = True) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(cmd)}")
    if dry:
        return subprocess.CompletedProcess(cmd, 0, "", "")
    return subprocess.run(cmd, check=check, text=True)


def ensure_target_dir(dry: bool) -> None:
    banner("1) Prepare /opt/storage/llmgateway")
    if not NEW_DATA.parent.exists():
        sys.exit(f"  /opt/storage does not exist or is not mounted")
    for sub in ("", "config", "logs", "backups", "docker-volumes",
                "hf-cache", "venv"):
        p = NEW_DATA / sub if sub else NEW_DATA
        print(f"  mkdir -p {p}")
        if not dry:
            p.mkdir(parents=True, exist_ok=True)


def stop_services(dry: bool) -> None:
    banner("2) Stop gateway + docker stack")
    if PLIST.exists():
        run(["launchctl", "unload", str(PLIST)], dry, check=False)
    if COMPOSE.exists():
        # Use the old compose (named volumes) to bring stack down cleanly;
        # since we already edited compose to bind-mounts, just stop containers.
        run(["docker", "compose", "-f", str(COMPOSE), "down"],
            dry, check=False)


def rsync_app_data(dry: bool) -> None:
    banner("3) rsync app state ~/.llm-gateway → /opt/storage/llmgateway")
    if not OLD_DATA.exists():
        print(f"  {OLD_DATA} doesn't exist — skipping")
        return
    # rsync top-level files and named subdirs; skip the venv (rebuilt) and
    # the duplicated whisper model (already at /opt/storage/whisper).
    cmd = [
        "rsync", "-aHv", "--exclude=venv", "--exclude=whisper",
        f"{OLD_DATA}/", f"{NEW_DATA}/",
    ]
    run(cmd, dry)


def rebuild_mlx_venv(dry: bool) -> None:
    banner("4) Rebuild mlx_audio venv at /opt/storage/llmgateway/venv")
    venv = NEW_DATA / "venv"
    if venv.exists() and any(venv.iterdir()):
        if (venv / "bin" / "mlx_audio.server").exists():
            print(f"  venv already populated — skipping rebuild")
            return
    # Homebrew Python on macOS rejects --copies; symlinks are fine because
    # the venv lives at its final on-disk home and won't be relocated.
    run(["python3", "-m", "venv", str(venv)], dry)
    pip = venv / "bin" / "pip"
    run([str(pip), "install", "--upgrade", "pip"], dry)
    # mlx-audio pulls mlx, mlx-lm, transformers, etc. (~1.5 G)
    run([str(pip), "install", "mlx-audio"], dry)


def migrate_hf_cache(dry: bool) -> None:
    banner("5) Move HuggingFace cache → /opt/storage/llmgateway/hf-cache")
    if not OLD_HF.exists():
        print("  no existing HF cache — skipping")
        return
    run(["rsync", "-aHv", f"{OLD_HF}/", f"{NEW_HF}/"], dry)


def migrate_docker_volumes(dry: bool) -> None:
    banner("6) Copy each docker named volume → bind-mount dir")
    # `docker volume inspect` first; skip missing.
    for vol, dest in VOLUME_MAP.items():
        inspect = subprocess.run(
            ["docker", "volume", "inspect", vol],
            capture_output=True, text=True,
        )
        if inspect.returncode != 0:
            print(f"  {vol}: not present — skipping")
            continue
        print(f"  {vol}  →  {dest}")
        if not dry:
            dest.mkdir(parents=True, exist_ok=True)
        # Use alpine to cp -a from the named volume into the bind-mount path.
        # The bind source is on the macOS host (mounted into the helper
        # container as /to).
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{vol}:/from",
            "-v", f"{dest}:/to",
            "alpine", "sh", "-c", "cp -a /from/. /to/",
        ]
        run(cmd, dry)


def reinstall_launchd(dry: bool) -> None:
    banner("7) Reinstall launchd plist with new data dir")
    env = os.environ.copy()
    env["LLM_GATEWAY_DATA_DIR"] = str(NEW_DATA)
    py = REPO_DIR / ".venv" / "bin" / "python3"
    cmd = [str(py), str(REPO_DIR / "scripts" / "llmgateway.py"), "--install"]
    print(f"  $ LLM_GATEWAY_DATA_DIR={NEW_DATA} {' '.join(cmd)}")
    if not dry:
        subprocess.run(cmd, env=env, check=False)


def relaunch_stack(dry: bool) -> None:
    banner("8) Bring docker stack back up (now bind-mounted)")
    env_file = NEW_DATA / ".env"
    cmd = ["docker", "compose", "-f", str(COMPOSE)]
    if env_file.exists():
        cmd += ["--env-file", str(env_file)]
    cmd += ["up", "-d"]
    run(cmd, dry, check=False)


def summarize(dry: bool) -> None:
    banner("9) Done — leftovers you can remove once verified")
    print(f"  {OLD_DATA}     (will be safe to rm -rf after a smoke test)")
    print(f"  {OLD_HF}        (HF cache copy; remove after first request succeeds)")
    print(f"  docker named volumes: " + " ".join(VOLUME_MAP))
    print("    (remove via: docker volume rm <name> after stack is healthy)")
    if dry:
        print("\n  (dry-run — no changes made)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="Print every action without executing")
    args = ap.parse_args()
    dry = args.dry_run

    ensure_target_dir(dry)
    stop_services(dry)
    rsync_app_data(dry)
    rebuild_mlx_venv(dry)
    migrate_hf_cache(dry)
    migrate_docker_volumes(dry)
    reinstall_launchd(dry)
    relaunch_stack(dry)
    summarize(dry)
    return 0


if __name__ == "__main__":
    sys.exit(main())
