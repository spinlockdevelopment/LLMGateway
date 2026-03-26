"""Tests for config schema validation with new DMR/whisper/llmfit shape."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from config.schema import validate_config


def test_valid_minimal_config():
    config = {
        "gateway": {"host": "127.0.0.1", "port": 8080, "log_level": "INFO"},
    }
    errors, warnings = validate_config(config)
    assert errors == []


def test_valid_full_config():
    config = {
        "gateway": {"host": "127.0.0.1", "port": 8080, "log_level": "INFO"},
        "docker_model_runner": {
            "enabled": True,
            "host": "localhost",
            "port": 12434,
            "api_base": "http://localhost:12434/engines/v1",
        },
        "services": {
            "whisper": {
                "enabled": False,
                "binary": "whisper-server",
                "args": {"--host": "127.0.0.1", "--port": "8178"},
                "health_check_url": "http://localhost:8178/health",
            },
        },
        "llmfit": {"auto_recommend_on_setup": True, "default_limit": 5},
        "docker": {"auto_launch": True, "compose_file": "docker/docker-compose.yml"},
    }
    errors, warnings = validate_config(config)
    assert errors == []


def test_dmr_port_validation():
    config = {
        "docker_model_runner": {"enabled": True, "port": 99999},
    }
    errors, _ = validate_config(config)
    assert any("docker_model_runner.port" in e for e in errors)


def test_dmr_api_base_url_validation():
    config = {
        "docker_model_runner": {"enabled": True, "port": 12434, "api_base": "not-a-url"},
    }
    errors, _ = validate_config(config)
    assert any("api_base" in e for e in errors)


def test_dmr_port_conflicts_with_gateway():
    config = {
        "gateway": {"port": 12434},
        "docker_model_runner": {"enabled": True, "port": 12434},
    }
    errors, _ = validate_config(config)
    assert any("conflict" in e.lower() for e in errors)


def test_llmfit_section_must_be_dict():
    config = {"llmfit": "invalid"}
    errors, _ = validate_config(config)
    assert any("llmfit" in e for e in errors)


def test_services_whisper_only():
    """After migration, services section only contains whisper-type entries."""
    config = {
        "services": {
            "whisper": {
                "enabled": True,
                "binary": "whisper-server",
                "health_check_url": "http://localhost:8178/health",
            },
        },
    }
    errors, _ = validate_config(config)
    assert errors == []
