"""Docker Model Runner wrapper.

Thin layer over Docker Model Runner REST API (OpenAI-compatible model listing)
and Docker CLI (model pull/remove/inspect). Does NOT manage the DMR process —
Docker Desktop owns that.
"""
import asyncio
import json
import logging

import httpx

log = logging.getLogger("llm-gateway")


class DockerModelRunner:
    """Wrapper for Docker Model Runner REST API and CLI operations."""

    def __init__(self, host: str, port: int, api_base: str):
        self.host = host
        self.port = port
        self.api_base = api_base.rstrip("/")
        self._client = httpx.AsyncClient(timeout=10.0)

    async def close(self) -> None:
        """Close the shared HTTP client."""
        await self._client.aclose()

    async def is_available(self) -> bool:
        """Return True if the DMR REST API responds with HTTP 200."""
        try:
            resp = await self._client.get(f"{self.api_base}/models")
            return resp.status_code == 200
        except Exception as exc:
            log.debug("Docker Model Runner not available: %s", exc)
            return False

    async def list_models(self) -> list[dict]:
        """Return the list of models from the DMR REST API.

        Returns an empty list on any error (caller can use is_available()
        separately when the distinction matters).
        """
        try:
            resp = await self._client.get(f"{self.api_base}/models")
            resp.raise_for_status()
            return resp.json().get("data", [])
        except Exception as exc:
            log.warning("Failed to list DMR models: %s", exc)
            return []

    async def pull_model(self, name: str) -> tuple[bool, str]:
        """Pull a model via the Docker CLI. Returns (success, output)."""
        rc, stdout, stderr = await self._run_docker("pull", name, timeout=1800)
        if rc != 0:
            err = stderr.decode().strip()
            log.error("docker model pull %s failed: %s", name, err)
            return False, err
        return True, stdout.decode().strip()

    async def pull_model_stream(self, name: str):
        """Async generator that yields (line, done, success) as docker model pull runs."""
        proc = await asyncio.create_subprocess_exec(
            "docker", "model", "pull", name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            # Docker outputs pull progress to stderr
            async def read_lines(stream):
                while True:
                    line = await asyncio.wait_for(stream.readline(), timeout=300)
                    if not line:
                        break
                    yield line.decode(errors="replace").rstrip("\n\r")

            async for line in read_lines(proc.stderr):
                yield line, False, False
            async for line in read_lines(proc.stdout):
                yield line, False, False

            await asyncio.wait_for(proc.wait(), timeout=30)
            yield "", True, proc.returncode == 0
        except asyncio.TimeoutError:
            proc.kill()
            yield "Timed out", True, False
        except Exception as e:
            proc.kill()
            yield str(e), True, False

    async def remove_model(self, name: str) -> bool:
        """Remove a model via the Docker CLI."""
        rc, _, stderr = await self._run_docker("rm", name, timeout=60)
        if rc != 0:
            log.error("docker model rm %s failed: %s", name, stderr.decode().strip())
            return False
        return True

    async def inspect_model(self, name: str) -> dict | None:
        """Inspect a model via the Docker CLI. Returns parsed JSON or None."""
        rc, stdout, stderr = await self._run_docker("inspect", name, timeout=30)
        if rc != 0:
            log.error("docker model inspect %s failed: %s", name, stderr.decode().strip())
            return None
        try:
            return json.loads(stdout.decode())
        except json.JSONDecodeError as exc:
            log.error("Failed to parse inspect output for %s: %s", name, exc)
            return None

    async def _run_docker(self, subcmd: str, name: str, timeout: int = 60
                          ) -> tuple[int, bytes, bytes]:
        """Run `docker model <subcmd> <name>` and return (returncode, stdout, stderr)."""
        proc = await asyncio.create_subprocess_exec(
            "docker", "model", subcmd, name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return -1, b"", f"Timed out after {timeout}s".encode()
        return proc.returncode, stdout, stderr

    def status_dict(self, available: bool, models_count: int) -> dict:
        """Return a summary dict suitable for API health/status responses."""
        return {
            "available": available,
            "models_count": models_count,
            "host": self.host,
            "port": self.port,
            "api_base": self.api_base,
        }
