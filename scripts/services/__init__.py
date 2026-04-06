"""
Service components for LLM Gateway.

- DockerModelRunner: Docker Model Runner REST API + CLI wrapper
- WhisperManager: Standalone whisper.cpp process manager
- LlmfitClient: llmfit CLI wrapper for model recommendations

Shared async helpers live here so service modules don't duplicate them.
"""

from __future__ import annotations

import asyncio

import httpx


async def run_cmd(cmd: list[str], timeout: int = 10) -> tuple[int, str, str]:
    """Run a command asynchronously and return (returncode, stdout, stderr).

    Returns (-1, "", "") on timeout, missing binary, or OS errors.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode, stdout.decode(errors="replace"), stderr.decode(errors="replace")
    except (asyncio.TimeoutError, FileNotFoundError, OSError):
        return -1, "", ""


async def http_ok(url: str, timeout: float = 2) -> bool:
    """Return True if a GET to *url* returns a 2xx/3xx status."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
            return 200 <= resp.status_code < 400
    except Exception:
        return False
