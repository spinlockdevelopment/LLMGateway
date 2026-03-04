"""Application settings loaded from environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global application settings."""

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}

    # Server
    gateway_host: str = "0.0.0.0"
    gateway_port: int = 8000
    gateway_log_level: str = "info"

    # Config paths
    routing_config: Path = Path("config/routing.yaml")
    providers_config: Path = Path("config/providers.yaml")
    agents_config: Path = Path("config/agents.yaml")
    local_models_config: Path = Path("config/local_models.yaml")

    # Provider keys
    openrouter_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""

    # OpenTelemetry
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "llm-gateway"

    # Database
    usage_db_path: Path = Path("data/usage.db")

    # Rate limiting
    rate_limit_rpm: int = 60
    rate_limit_burst: int = 10

    # Local inference
    ollama_base_url: str = "http://localhost:11434"
    local_inference_timeout: int = 120
