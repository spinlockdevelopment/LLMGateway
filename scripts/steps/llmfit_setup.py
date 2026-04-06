"""
llmfit setup step.

Checks whether the llmfit CLI is available, installs it, and runs
model recommendations with an offer to pull selected models.
"""

from __future__ import annotations

import json
import shutil

from . import info, success, warn, provision, run


def _is_installed() -> bool:
    return shutil.which("llmfit") is not None


def _install() -> None:
    import sys
    info("  Installing llmfit via pip...")
    run([sys.executable, "-m", "pip", "install", "llmfit"], timeout=120)
    success("llmfit: installed")
    _run_recommendations()


def _run_recommendations() -> None:
    """Run llmfit recommend, present results, and offer to pull models."""
    info("  Running: llmfit recommend --json --limit 5 ...")
    result = run(
        ["llmfit", "recommend", "--json", "--limit", "5"],
        check=False, timeout=60,
    )
    if result.returncode != 0:
        warn("llmfit recommend failed (non-fatal). Run manually: llmfit recommend")
        return

    models = _parse_recommendations(result.stdout)
    if not models:
        info("  No recommendations returned by llmfit.")
        return

    info("  Recommended models for your hardware:")
    for i, model in enumerate(models, 1):
        name = model.get("name") or model.get("id") or str(model)
        desc = model.get("description") or model.get("size") or ""
        if desc:
            info(f"    {i}) {name}  ({desc})")
        else:
            info(f"    {i}) {name}")

    info("")
    info("  Enter the numbers of models to pull (e.g. 1,3) or press Enter to skip:")
    try:
        raw = input("  Pull models: ").strip()
    except (EOFError, KeyboardInterrupt):
        raw = ""

    if not raw:
        info("  Skipping model pull.")
        return

    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            idx = int(part) - 1
            if 0 <= idx < len(models):
                model = models[idx]
                name = model.get("name") or model.get("id") or str(model)
                info(f"  Pulling: docker model pull {name} ...")
                result = run(
                    ["docker", "model", "pull", name],
                    check=False, timeout=600,
                )
                if result.returncode == 0:
                    success(f"Pulled: {name}")
                else:
                    warn(f"Pull failed for {name} (exit {result.returncode})")


def _parse_recommendations(stdout: str) -> list[dict]:
    """Parse JSON output from llmfit recommend."""
    try:
        data = json.loads(stdout)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("models", "recommendations", "results"):
                if isinstance(data.get(key), list):
                    return data[key]
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def setup(dry_run: bool = False) -> bool:
    """Ensure llmfit is installed and run recommendations."""
    return provision(
        name="llmfit",
        is_ready=_is_installed,
        install=_install,
        dry_run=dry_run,
    )
