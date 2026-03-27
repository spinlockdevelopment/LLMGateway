"""llmfit CLI wrapper for hardware-aware model recommendations."""
from __future__ import annotations

import asyncio
import json
import logging
import shutil
from typing import Any

INSTALL_COMMAND = "curl -fsSL https://llmfit.axjns.dev/install.sh | sh"

log = logging.getLogger("llm-gateway")


class LlmfitClient:
    """Wrapper around the llmfit CLI tool."""

    def is_installed(self) -> bool:
        """Return True if the llmfit CLI is available on PATH."""
        return shutil.which("llmfit") is not None

    async def recommend(
        self,
        use_case: str | None = None,
        limit: int = 5,
    ) -> list[dict]:
        """Run llmfit recommend and return parsed recommendations.

        Returns an empty list if llmfit is not installed or the command fails.
        """
        if not self.is_installed():
            log.debug("llmfit is not installed; skipping recommend")
            return []

        cmd = ["llmfit", "recommend", "--json", "--limit", str(limit)]
        if use_case:
            cmd.extend(["--use-case", use_case])

        result = await self._run_json_cmd(cmd, timeout=60)
        return result if isinstance(result, list) else []

    async def system_info(self) -> dict | None:
        """Run llmfit system --json and return parsed system information.

        Returns None if llmfit is not installed or the command fails.
        """
        if not self.is_installed():
            log.debug("llmfit is not installed; skipping system_info")
            return None

        result = await self._run_json_cmd(["llmfit", "system", "--json"], timeout=30)
        return result if isinstance(result, dict) else None

    async def _run_json_cmd(self, cmd: list[str], timeout: int) -> Any:
        """Run a CLI command and parse its stdout as JSON. Returns None on failure."""
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            log.warning("%s timed out", cmd[1])
            return None
        except Exception as exc:
            log.warning("%s failed: %s", cmd[1], exc)
            return None

        if proc.returncode != 0:
            log.warning("%s exited %d: %s", cmd[1], proc.returncode, stderr.decode())
            return None

        try:
            return json.loads(stdout)
        except json.JSONDecodeError as exc:
            log.warning("%s returned invalid JSON: %s", cmd[1], exc)
            return None
