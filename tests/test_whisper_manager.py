"""Tests for standalone WhisperManager (no BaseService dependency)."""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from services.whisper_manager import WhisperManager


@pytest.fixture
def whisper_config():
    return {
        "enabled": True,
        "binary": "whisper-server",
        "args": {
            "--model": "/models/whisper/large-v3.bin",
            "--host": "127.0.0.1",
            "--port": "8178",
        },
        "extra_args": [],
        "health_check_url": "http://localhost:8178/health",
    }


@pytest.fixture
def whisper(whisper_config):
    return WhisperManager(whisper_config)


def test_initial_state_stopped(whisper):
    assert whisper.state == "stopped"


def test_disabled_state():
    mgr = WhisperManager({"enabled": False})
    assert mgr.state == "disabled"


def test_build_command(whisper):
    cmd = whisper._build_command()
    assert cmd[0] == "whisper-server"
    assert "--model" in cmd
    assert "/models/whisper/large-v3.bin" in cmd
    assert "--host" in cmd
    assert "127.0.0.1" in cmd


def test_status_dict(whisper):
    status = whisper.status_dict()
    assert status["name"] == "whisper"
    assert status["state"] == "stopped"


@pytest.mark.asyncio
async def test_start_disabled():
    mgr = WhisperManager({"enabled": False})
    result = await mgr.start()
    assert result is False
    assert mgr.state == "disabled"


@pytest.mark.asyncio
async def test_health_check_no_process():
    mgr = WhisperManager({"enabled": True, "binary": "whisper-server"})
    assert await mgr.health_check() is False
