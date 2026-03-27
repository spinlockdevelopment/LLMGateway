# tests/test_api.py
"""Tests for REST API endpoints."""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from web.api import create_api_router
from fastapi import FastAPI


@pytest.fixture
def app():
    app = FastAPI()

    dmr = AsyncMock()
    dmr.is_available = AsyncMock(return_value=True)
    dmr.list_models = AsyncMock(return_value=[
        {"id": "ai/qwen2.5-coder:7b", "object": "model"},
    ])
    dmr.status_dict = MagicMock(return_value={
        "available": True, "host": "localhost", "port": 12434,
        "api_base": "http://localhost:12434/engines/v1", "models_count": 1,
    })
    app.state.dmr = dmr

    llmfit_client = AsyncMock()
    llmfit_client.is_installed = MagicMock(return_value=True)
    llmfit_client.recommend = AsyncMock(return_value=[
        {"model": "ai/qwen2.5-coder:7b", "composite_score": 0.85},
    ])
    llmfit_client.system_info = AsyncMock(return_value={"cpu": "Apple M4 Max"})
    app.state.llmfit = llmfit_client

    whisper = MagicMock()
    whisper.enabled = True
    whisper.state = "stopped"
    whisper.status_dict = MagicMock(return_value={
        "name": "whisper", "state": "stopped", "pid": None,
    })
    app.state.whisper = whisper

    cm = MagicMock()
    cm.get_config_masked = MagicMock(return_value={"gateway": {"port": 8080}})
    app.state.config_manager = cm

    app.include_router(create_api_router(), prefix="/api")
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_dmr_status(client):
    resp = client.get("/api/dmr/status")
    assert resp.status_code == 200
    assert resp.json()["available"] is True


def test_list_models(client):
    resp = client.get("/api/models")
    assert resp.status_code == 200
    assert len(resp.json()["models"]) == 1


def test_llmfit_recommendations(client):
    resp = client.get("/api/llmfit/recommendations")
    assert resp.status_code == 200
    assert len(resp.json()["recommendations"]) == 1


def test_llmfit_system(client):
    resp = client.get("/api/llmfit/system")
    assert resp.status_code == 200
    assert resp.json()["system"]["cpu"] == "Apple M4 Max"


def test_status_includes_dmr_and_whisper(client):
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "dmr" in data
    assert "whisper" in data
