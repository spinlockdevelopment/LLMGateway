"""LLM Gateway — main FastAPI application."""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from pythonjsonlogger.json import JsonFormatter

from llm_gateway.api import admin, chat, messages, models
from llm_gateway.auth.tokens import TokenAuth
from llm_gateway.config.loader import ConfigManager
from llm_gateway.config.settings import Settings
from llm_gateway.local.manager import LocalModelManager
from llm_gateway.middleware.logging import RequestLoggingMiddleware
from llm_gateway.middleware.rate_limit import RateLimiter
from llm_gateway.providers.registry import ProviderRegistry
from llm_gateway.routing.engine import RoutingEngine
from llm_gateway.telemetry.otel import setup_telemetry
from llm_gateway.tracking.usage import UsageTracker

logger = logging.getLogger(__name__)


def _configure_logging(level: str) -> None:
    """Set up structured JSON logging to stdout."""
    handler = logging.StreamHandler(sys.stdout)
    formatter = JsonFormatter(
        fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level"},
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # Quiet noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("litellm").setLevel(logging.WARNING)
    logging.getLogger("opentelemetry").setLevel(logging.WARNING)


def _on_config_reload(changed: list[str]) -> None:
    """Callback when config files are reloaded."""
    logger.info("Config reloaded: %s", changed)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown."""
    settings: Settings = app.state.settings

    # Load all configs
    config_mgr = app.state.config_manager
    config_mgr.load("routing", settings.routing_config)
    config_mgr.load("providers", settings.providers_config)
    config_mgr.load("agents", settings.agents_config)
    config_mgr.load("local_models", settings.local_models_config)
    config_mgr.on_reload(_on_config_reload)

    # Initialize routing engine
    routing_engine: RoutingEngine = app.state.routing_engine
    routing_engine.load_config(config_mgr.get("routing"))

    # Initialize providers
    provider_registry: ProviderRegistry = app.state.provider_registry
    provider_registry.load_config(config_mgr.get("providers"), settings)

    # Initialize auth
    auth: TokenAuth = app.state.auth
    auth.load_config(config_mgr.get("agents"))

    # Initialize local model manager
    local_manager: LocalModelManager = app.state.local_manager
    local_manager.load_config(config_mgr.get("local_models"))
    await local_manager.initialize()

    # Initialize usage tracker
    usage_tracker: UsageTracker = app.state.usage_tracker
    await usage_tracker.initialize()

    # Wire up config reload to re-initialize components
    def _reload_handler(changed: list[str]) -> None:
        for name in changed:
            if name == "routing":
                routing_engine.load_config(config_mgr.get("routing"))
            elif name == "agents":
                auth.load_config(config_mgr.get("agents"))
            elif name == "local_models":
                local_manager.load_config(config_mgr.get("local_models"))
            elif name == "providers":
                provider_registry.load_config(config_mgr.get("providers"), settings)

    config_mgr.on_reload(_reload_handler)

    # Start background tasks
    await config_mgr.start_watching()
    await provider_registry.start_health_checks()

    logger.info("LLM Gateway started on %s:%s", settings.gateway_host, settings.gateway_port)

    yield

    # Shutdown
    await config_mgr.stop_watching()
    await provider_registry.stop_health_checks()
    await usage_tracker.close()
    await local_manager.close()
    logger.info("LLM Gateway shut down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = Settings()
    _configure_logging(settings.gateway_log_level)

    app = FastAPI(
        title="LLM Gateway",
        version="0.1.0",
        description="Local LLM routing gateway for Apple Silicon",
        lifespan=lifespan,
    )

    # Store shared state
    app.state.settings = settings
    app.state.config_manager = ConfigManager()
    app.state.routing_engine = RoutingEngine()
    app.state.provider_registry = ProviderRegistry()
    app.state.auth = TokenAuth()
    app.state.local_manager = LocalModelManager(ollama_base_url=settings.ollama_base_url)
    app.state.usage_tracker = UsageTracker(db_path=settings.usage_db_path)
    app.state.rate_limiter = RateLimiter(
        default_rpm=settings.rate_limit_rpm,
        burst=settings.rate_limit_burst,
    )

    # Setup telemetry (returns metrics recorder)
    app.state.metrics = setup_telemetry(
        app,
        service_name=settings.otel_service_name,
        otlp_endpoint=settings.otel_exporter_otlp_endpoint,
    )

    # Add middleware
    app.add_middleware(RequestLoggingMiddleware)

    # Register routes
    app.include_router(chat.router)
    app.include_router(messages.router)
    app.include_router(models.router)
    app.include_router(admin.router)

    return app


# Default app instance for uvicorn
app = create_app()

if __name__ == "__main__":
    import uvicorn

    s = Settings()
    uvicorn.run(
        "llm_gateway.main:app",
        host=s.gateway_host,
        port=s.gateway_port,
        log_level=s.gateway_log_level,
        reload=False,
    )
