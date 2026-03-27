"""Docker Model Runner wrapper.

Thin layer over Docker Model Runner REST API (OpenAI-compatible model listing)
and Docker CLI (model pull/remove/inspect). Does NOT manage the DMR process —
Docker Desktop owns that.
"""
import asyncio
import json
import logging

import httpx

logger = logging.getLogger(__name__)


class DockerModelRunner:
    """Wrapper for Docker Model Runner REST API and CLI operations."""

    def __init__(self, host: str, port: int, api_base: str):
        self.host = host
        self.port = port
        self.api_base = api_base.rstrip("/")

    async def is_available(self) -> bool:
        """Return True if the DMR REST API responds with HTTP 200."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.api_base}/models")
                return response.status_code == 200
        except Exception as exc:
            logger.debug("Docker Model Runner not available: %s", exc)
            return False

    async def list_models(self) -> list[dict]:
        """Return the list of models from the DMR REST API."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{self.api_base}/models")
            response.raise_for_status()
            data = await response.json()
            return data.get("data", [])

    async def pull_model(self, name: str) -> tuple[bool, str]:
        """Pull a model via the Docker CLI. Returns (success, output)."""
        args = ["docker", "model", "pull", name]
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=1800)
        except asyncio.TimeoutError:
            proc.kill()
            return False, "Timed out waiting for model pull"

        output = stdout.decode().strip()
        if proc.returncode != 0:
            err = stderr.decode().strip()
            logger.error("docker model pull %s failed: %s", name, err)
            return False, err
        return True, output

    async def remove_model(self, name: str) -> bool:
        """Remove a model via the Docker CLI."""
        args = ["docker", "model", "rm", name]
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            err = stderr.decode().strip()
            logger.error("docker model rm %s failed: %s", name, err)
            return False
        return True

    async def inspect_model(self, name: str) -> dict | None:
        """Inspect a model via the Docker CLI. Returns parsed JSON or None."""
        args = ["docker", "model", "inspect", name]
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            err = stderr.decode().strip()
            logger.error("docker model inspect %s failed: %s", name, err)
            return None
        try:
            return json.loads(stdout.decode())
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse inspect output for %s: %s", name, exc)
            return None

    def status_dict(self, available: bool, models_count: int) -> dict:
        """Return a summary dict suitable for API health/status responses."""
        return {
            "available": available,
            "models_count": models_count,
            "host": self.host,
            "port": self.port,
            "api_base": self.api_base,
        }
