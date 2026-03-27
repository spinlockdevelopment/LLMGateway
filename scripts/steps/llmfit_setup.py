"""
llmfit setup step.

Checks whether the llmfit CLI is available, optionally installs it,
runs model recommendations, and offers to pull selected models via
`docker model pull`.
"""

from __future__ import annotations

import json
import shutil
from typing import Optional

from . import ProvisioningStep, log, run

_LLMFIT_INSTALL_CMD = "pip install llmfit"


class LlmfitSetup(ProvisioningStep):
    """
    Ensures llmfit is available and walks the user through pulling
    recommended models into Docker Model Runner.

    - install():  pip install llmfit
    - is_installed(): shutil.which("llmfit")
    - _on_already_installed(): runs recommendations + pull flow.
    """

    name = "llmfit"

    # ── Interface ─────────────────────────────────────────────────────────────

    def is_installed(self) -> bool:
        return shutil.which("llmfit") is not None

    def current_version(self) -> Optional[str]:
        if not self.is_installed():
            return None
        result = run(["llmfit", "--version"], check=False, timeout=10)
        if result.returncode == 0:
            return result.stdout.strip() or result.stderr.strip() or "installed"
        return None

    def install(self) -> None:
        log.info("  Installing llmfit via pip...")
        run(["pip", "install", "llmfit"], timeout=120)
        log.info("  llmfit installed")

    # ── Already-installed hook ────────────────────────────────────────────────

    def _on_already_installed(self) -> None:
        log.info(f"  llmfit: {self.current_version() or 'installed'}")
        self._run_recommendations()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _run_recommendations(self) -> None:
        """Run llmfit recommend, present results, and offer to pull models."""
        log.info("  Running: llmfit recommend --json --limit 5 ...")
        result = run(
            ["llmfit", "recommend", "--json", "--limit", "5"],
            check=False,
            timeout=60,
        )
        if result.returncode != 0:
            log.warning(
                "  llmfit recommend failed (non-fatal). "
                "You can run it manually later: llmfit recommend"
            )
            return

        models = self._parse_recommendations(result.stdout)
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

        self._prompt_and_pull(models)

    def _parse_recommendations(self, stdout: str) -> list[dict]:
        """Parse JSON output from llmfit recommend. Returns [] on failure."""
        try:
            data = json.loads(stdout)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                # Accept {"models": [...]} or {"recommendations": [...]}
                for key in ("models", "recommendations", "results"):
                    if isinstance(data.get(key), list):
                        return data[key]
        except (json.JSONDecodeError, TypeError):
            pass
        return []

    def _prompt_and_pull(self, models: list[dict]) -> None:
        """Ask the user which models to pull and run docker model pull."""
        log.info("")
        log.info("  Enter the numbers of models to pull (e.g. 1,3) or press Enter to skip:")
        try:
            raw = input("  Pull models: ").strip()
        except (EOFError, KeyboardInterrupt):
            raw = ""

        if not raw:
            log.info("  Skipping model pull.")
            return

        selected: list[dict] = []
        for part in raw.split(","):
            part = part.strip()
            if part.isdigit():
                idx = int(part) - 1
                if 0 <= idx < len(models):
                    selected.append(models[idx])

        if not selected:
            log.info("  No valid selection — skipping model pull.")
            return

        for model in selected:
            name = model.get("name") or model.get("id") or str(model)
            log.info(f"  Pulling: docker model pull {name} ...")
            result = run(
                ["docker", "model", "pull", name],
                check=False,
                timeout=600,
            )
            if result.returncode == 0:
                log.info(f"  Pulled: {name}")
            else:
                log.warning(f"  Pull failed for {name} (exit {result.returncode})")
