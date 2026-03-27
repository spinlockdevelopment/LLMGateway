# tests/test_llmfit.py
"""Tests for llmfit CLI wrapper."""
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from services.llmfit import LlmfitClient


@pytest.fixture
def llmfit():
    return LlmfitClient()


def test_is_installed_true(llmfit):
    with patch("shutil.which", return_value="/usr/local/bin/llmfit"):
        assert llmfit.is_installed() is True


def test_is_installed_false(llmfit):
    with patch("shutil.which", return_value=None):
        assert llmfit.is_installed() is False


@pytest.mark.asyncio
async def test_recommend_success(llmfit):
    recommendations = [
        {"model": "ai/qwen2.5-coder:7b", "composite_score": 0.85,
         "memory_fit": 0.9, "quality": 0.8, "speed": 0.85},
    ]
    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(
        return_value=(json.dumps(recommendations).encode(), b"")
    )
    mock_proc.returncode = 0

    with patch("shutil.which", return_value="/usr/local/bin/llmfit"):
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await llmfit.recommend(limit=5)
            assert len(result) == 1
            assert result[0]["model"] == "ai/qwen2.5-coder:7b"


@pytest.mark.asyncio
async def test_recommend_not_installed(llmfit):
    with patch("shutil.which", return_value=None):
        result = await llmfit.recommend()
        assert result == []


@pytest.mark.asyncio
async def test_recommend_with_use_case(llmfit):
    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(b"[]", b""))
    mock_proc.returncode = 0

    with patch("shutil.which", return_value="/usr/local/bin/llmfit"):
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            await llmfit.recommend(use_case="coding", limit=3)
            call_args = mock_exec.call_args[0]
            assert "--use-case" in call_args
            assert "coding" in call_args


@pytest.mark.asyncio
async def test_system_info(llmfit):
    sys_info = {"cpu": "Apple M4 Max", "ram_gb": 128, "gpu": "Apple Metal"}
    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(
        return_value=(json.dumps(sys_info).encode(), b"")
    )
    mock_proc.returncode = 0

    with patch("shutil.which", return_value="/usr/local/bin/llmfit"):
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await llmfit.system_info()
            assert result["cpu"] == "Apple M4 Max"


@pytest.mark.asyncio
async def test_system_info_not_installed(llmfit):
    with patch("shutil.which", return_value=None):
        result = await llmfit.system_info()
        assert result is None
