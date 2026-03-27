# tests/test_docker_model_runner.py
"""Tests for Docker Model Runner wrapper."""
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from services.docker_model_runner import DockerModelRunner


@pytest.fixture
def dmr():
    return DockerModelRunner(
        host="localhost",
        port=12434,
        api_base="http://localhost:12434/engines/v1",
    )


@pytest.mark.asyncio
async def test_is_available_success(dmr):
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": []}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await dmr.is_available()
        assert result is True


@pytest.mark.asyncio
async def test_is_available_connection_error(dmr):
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client_cls.return_value = mock_client

        result = await dmr.is_available()
        assert result is False


@pytest.mark.asyncio
async def test_list_models(dmr):
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = lambda: None
    mock_response.json.return_value = {
        "data": [
            {"id": "ai/qwen2.5-coder:7b", "object": "model"},
            {"id": "ai/llama3.2:3b", "object": "model"},
        ]
    }

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        models = await dmr.list_models()
        assert len(models) == 2
        assert models[0]["id"] == "ai/qwen2.5-coder:7b"


@pytest.mark.asyncio
async def test_pull_model(dmr):
    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(b"Downloaded ai/qwen2.5-coder:7b\n", b""))
    mock_proc.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        ok, output = await dmr.pull_model("ai/qwen2.5-coder:7b")
        assert ok is True
        assert "Downloaded" in output


@pytest.mark.asyncio
async def test_remove_model(dmr):
    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(b"", b""))
    mock_proc.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        ok = await dmr.remove_model("ai/qwen2.5-coder:7b")
        assert ok is True


@pytest.mark.asyncio
async def test_inspect_model(dmr):
    inspect_data = {"Name": "ai/qwen2.5-coder:7b", "Size": "4.5GB"}
    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(json.dumps(inspect_data).encode(), b""))
    mock_proc.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        info = await dmr.inspect_model("ai/qwen2.5-coder:7b")
        assert info["Name"] == "ai/qwen2.5-coder:7b"


def test_status_dict(dmr):
    status = dmr.status_dict(available=True, models_count=3)
    assert status["available"] is True
    assert status["models_count"] == 3
    assert status["port"] == 12434
