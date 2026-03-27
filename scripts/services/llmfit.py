"""llmfit CLI wrapper for hardware-aware model recommendations."""
import asyncio
import json
import logging
import shutil
from typing import Optional

INSTALL_COMMAND = "curl -fsSL https://llmfit.axjns.dev/install.sh | sh"

logger = logging.getLogger("llm-gateway")


class LlmfitClient:
    """Wrapper around the llmfit CLI tool."""

    def is_installed(self) -> bool:
        """Return True if the llmfit CLI is available on PATH."""
        return shutil.which("llmfit") is not None

    async def recommend(
        self,
        use_case: Optional[str] = None,
        limit: int = 5,
    ) -> list[dict]:
        """Run llmfit recommend and return parsed recommendations.

        Returns an empty list if llmfit is not installed or the command fails.
        """
        if not self.is_installed():
            logger.debug("llmfit is not installed; skipping recommend")
            return []

        cmd = ("llmfit", "recommend", "--json", "--limit", str(limit))
        if use_case:
            cmd += ("--use-case", use_case)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        except asyncio.TimeoutError:
            logger.warning("llmfit recommend timed out")
            return []
        except Exception as exc:
            logger.warning("llmfit recommend failed: %s", exc)
            return []

        if proc.returncode != 0:
            logger.warning("llmfit recommend exited %d: %s", proc.returncode, stderr.decode())
            return []

        try:
            return json.loads(stdout)
        except json.JSONDecodeError as exc:
            logger.warning("llmfit recommend returned invalid JSON: %s", exc)
            return []

    async def system_info(self) -> Optional[dict]:
        """Run llmfit system --json and return parsed system information.

        Returns None if llmfit is not installed or the command fails.
        """
        if not self.is_installed():
            logger.debug("llmfit is not installed; skipping system_info")
            return None

        cmd = ("llmfit", "system", "--json")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        except asyncio.TimeoutError:
            logger.warning("llmfit system timed out")
            return None
        except Exception as exc:
            logger.warning("llmfit system failed: %s", exc)
            return None

        if proc.returncode != 0:
            logger.warning("llmfit system exited %d: %s", proc.returncode, stderr.decode())
            return None

        try:
            return json.loads(stdout)
        except json.JSONDecodeError as exc:
            logger.warning("llmfit system returned invalid JSON: %s", exc)
            return None
