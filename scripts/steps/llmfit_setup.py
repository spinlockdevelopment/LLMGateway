"""
llmfit setup step.

Checks whether the llmfit CLI is available, installs it, and runs
model recommendations with an offer to pull selected models.
"""

from __future__ import annotations

import json
import shutil

from . import log, provision, run


def _is_installed() -> bool:
    return shutil.which("llmfit") is not None


def _install() -> None:
    import sys
    log.info("  Installing llmfit via pip...")
    run([sys.executable, "-m", "pip", "install", "llmfit"], timeout=120)
    log.info("  llmfit installed")
    _run_recommendations()


def _run_recommendations() -> None:
    """Run llmfit recommend, present results, and offer to pull models."""
    log.info("  Running: llmfit recommend --json --limit 5 ...")
    result = run(
        ["llmfit", "recommend", "--json", "--limit", "5"],
        check=False, timeout=60,
    )
    if result.returncode != 0:
        log.warning("  llmfit recommend failed (non-fatal). Run manually: llmfit recommend")
        return

    models = _parse_recommendations(result.stdout)
    if not models:
        log.info("  No recommendations returned by llmfit.")
        return

    log.info("  Recommended models for your hardware:")
    for i, model in enumerate(models, 1):
        name = model.get("name") or model.get("id") or str(model)
        desc = model.get("description") or model.get("size") or ""
        if desc:
            log.info(f"    {i}) {name}  ({desc})")
        else:
            log.info(f"    {i}) {name}")

    log.info("")
    log.info("  Enter the numbers of models to pull (e.g. 1,3) or press Enter to skip:")
    try:
        raw = input("  Pull models: ").strip()
    except (EOFError, KeyboardInterrupt):
        raw = ""

    if not raw:
        log.info("  Skipping model pull.")
        return

    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            idx = int(part) - 1
            if 0 <= idx < len(models):
                model = models[idx]
                name = model.get("name") or model.get("id") or str(model)
                log.info(f"  Pulling: docker model pull {name} ...")
                result = run(
                    ["docker", "model", "pull", name],
                    check=False, timeout=600,
                )
                if result.returncode == 0:
                    log.info(f"  Pulled: {name}")
                else:
                    log.warning(f"  Pull failed for {name} (exit {result.returncode})")


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
