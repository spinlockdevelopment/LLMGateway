"""
Git installation and repository update provisioning step.

Ensures git is installed via Homebrew. When already installed, attempts a
fast-forward pull of the repository so subsequent steps run against the
latest code. Pull failures are non-fatal (warnings only).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from . import ProvisioningStep, command_exists, log, run


class GitRepo(ProvisioningStep):
    """
    Ensures git is installed, then pulls the latest changes in the repo.

    - install():  brew install git
    - upgrade():  brew upgrade git
    - _on_already_installed(): checks brew outdated, upgrades if needed,
                               then fast-forward pulls the working repo.
    """

    name = "Git"

    def __init__(self, repo_dir: Path) -> None:
        self.repo_dir = repo_dir

    # ── Interface ─────────────────────────────────────────────────────────────

    def is_installed(self) -> bool:
        return command_exists("git")

    def current_version(self) -> Optional[str]:
        if not self.is_installed():
            return None
        result = run(["git", "--version"], check=False)
        return result.stdout.strip() if result.returncode == 0 else None

    def latest_version(self) -> Optional[str]:
        """Query Homebrew for the latest available git formula version."""
        if not command_exists("brew"):
            return None
        result = run(["brew", "info", "--json=v2", "git"], check=False, timeout=30)
        if result.returncode != 0:
            return None
        try:
            data = json.loads(result.stdout)
            formulae = data.get("formulae", [])
            if formulae:
                return formulae[0].get("versions", {}).get("stable")
        except (json.JSONDecodeError, KeyError, IndexError):
            pass
        return None

    def install(self) -> None:
        log.info("  Installing git via Homebrew...")
        run(["brew", "install", "git"], timeout=300)

    def upgrade(self) -> None:
        log.info("  Upgrading git via Homebrew...")
        run(["brew", "upgrade", "git"], check=False, timeout=300)

    # ── Already-installed hook ────────────────────────────────────────────────

    def _on_already_installed(self) -> None:
        # Check Homebrew for a newer formula version
        result = run(["brew", "outdated", "git"], check=False, timeout=30)
        if result.returncode == 0 and result.stdout.strip():
            log.info("  Git upgrade available via Homebrew — upgrading...")
            self.upgrade()
            log.info(f"  Upgraded to: {self.current_version()}")
        else:
            log.info(f"  Git: up to date")

        # Pull latest repo changes (best-effort, non-fatal)
        self._pull_repo()

    def _pull_repo(self) -> None:
        """Fast-forward pull in repo_dir. Logs warnings on failure; never raises."""
        git_dir = self.repo_dir / ".git"
        if not git_dir.is_dir():
            log.info(f"  {self.repo_dir} is not a git repository — skipping pull")
            return

        log.info(f"  Pulling latest changes in {self.repo_dir}...")
        result = run(
            ["git", "-C", str(self.repo_dir), "pull", "--ff-only"],
            check=False,
            timeout=60,
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            if "Already up to date" in output or "Already up-to-date" in output:
                log.info("  Repository: already up to date")
            else:
                log.info(f"  Repository updated: {output[:200]}")
        else:
            log.warning(
                "  Could not fast-forward pull — local uncommitted changes "
                "or detached HEAD. Continuing with existing code."
            )
