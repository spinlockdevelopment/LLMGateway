# tests/test_ui.py
"""Tests for UI action endpoints."""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from web.ui import create_ui_router
from fastapi import FastAPI


@pytest.fixture
def app(tmp_path):
    app = FastAPI()

    dmr = AsyncMock()
    dmr.pull_model = AsyncMock(return_value=(True, "Downloaded ai/qwen2.5-coder:7b"))
    dmr.remove_model = AsyncMock(return_value=True)
    app.state.dmr = dmr

    whisper = AsyncMock()
    whisper.enabled = True
    whisper.state = "stopped"
    whisper.start = AsyncMock(return_value=True)
    whisper.stop = AsyncMock(return_value=True)
    whisper.restart = AsyncMock(return_value=True)
    whisper.status_dict = MagicMock(return_value={"name": "whisper", "state": "running"})
    app.state.whisper = whisper

    cm = MagicMock()
    app.state.config_manager = cm

    app.state.repo_dir = tmp_path / "repo"
    app.state.repo_dir.mkdir()
    app.state.data_dir = tmp_path / "data"
    app.state.data_dir.mkdir()

    app.include_router(create_ui_router())
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def test_pull_model(client):
    resp = client.post("/ui/models/pull", json={"model": "ai/qwen2.5-coder:7b"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"


def test_pull_model_empty_name(client):
    resp = client.post("/ui/models/pull", json={"model": ""})
    assert resp.status_code == 400


def test_remove_model(client):
    resp = client.delete("/ui/models/ai%2Fqwen2.5-coder%3A7b")
    assert resp.status_code == 200
    assert resp.json()["status"] == "removed"


def test_whisper_start(client):
    resp = client.post("/ui/whisper/start")
    assert resp.status_code == 200


def test_whisper_stop(client):
    resp = client.post("/ui/whisper/stop")
    assert resp.status_code == 200


def test_whisper_restart(client):
    resp = client.post("/ui/whisper/restart")
    assert resp.status_code == 200
