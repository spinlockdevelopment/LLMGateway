"""Local model manager for Apple Silicon inference runtimes."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class LocalModel:
    """A locally-available model definition."""

    name: str
    runtime: str  # "ollama", "mlx", "llamacpp"
    model_path: str  # model identifier or file path
    context_length: int = 4096
    auto_load: bool = False
    parameters: dict[str, Any] = field(default_factory=dict)


class LocalModelManager:
    """Manages local LLM models running on Apple Silicon via Ollama/MLX/llama.cpp."""

    def __init__(self, ollama_base_url: str = "http://localhost:11434") -> None:
        self._models: dict[str, LocalModel] = {}
        self._loaded: set[str] = set()
        self._ollama_url = ollama_base_url
        self._client = httpx.AsyncClient(timeout=300)

    def load_config(self, config: dict[str, Any]) -> None:
        """Load local model definitions from config."""
        models = config.get("models", {})
        self._models.clear()
        for name, cfg in models.items():
            self._models[name] = LocalModel(
                name=name,
                runtime=cfg.get("runtime", "ollama"),
                model_path=cfg.get("model_path", name),
                context_length=cfg.get("context_length", 4096),
                auto_load=cfg.get("auto_load", False),
                parameters=cfg.get("parameters", {}),
            )
        logger.info("Configured %d local models", len(self._models))

    async def initialize(self) -> None:
        """Auto-load models marked for startup loading."""
        for name, model in self._models.items():
            if model.auto_load:
                try:
                    await self.load_model(name)
                except Exception as e:
                    logger.error("Failed to auto-load model %s: %s", name, e)

    async def load_model(self, name: str) -> dict[str, Any]:
        """Load a model into memory via its runtime."""
        model = self._models.get(name)
        if model is None:
            return {"error": f"Unknown model: {name}"}

        if model.runtime == "ollama":
            return await self._ollama_pull(model)
        elif model.runtime == "mlx":
            # MLX models are loaded on-demand by the mlx-lm server
            self._loaded.add(name)
            return {"status": "ready", "model": name, "runtime": "mlx"}
        elif model.runtime == "llamacpp":
            self._loaded.add(name)
            return {"status": "ready", "model": name, "runtime": "llamacpp"}
        else:
            return {"error": f"Unknown runtime: {model.runtime}"}

    async def unload_model(self, name: str) -> dict[str, Any]:
        """Unload a model from memory."""
        model = self._models.get(name)
        if model is None:
            return {"error": f"Unknown model: {name}"}

        if model.runtime == "ollama":
            # Send a generate request with keep_alive=0 to unload
            try:
                resp = await self._client.post(
                    f"{self._ollama_url}/api/generate",
                    json={"model": model.model_path, "keep_alive": 0},
                )
                self._loaded.discard(name)
                return {"status": "unloaded", "model": name}
            except Exception as e:
                return {"error": str(e)}

        self._loaded.discard(name)
        return {"status": "unloaded", "model": name}

    async def status(self) -> dict[str, Any]:
        """Return status of all configured local models."""
        ollama_running = await self._check_ollama()

        model_status = {}
        for name, model in self._models.items():
            model_status[name] = {
                "runtime": model.runtime,
                "model_path": model.model_path,
                "loaded": name in self._loaded,
                "context_length": model.context_length,
            }

        return {
            "ollama_running": ollama_running,
            "ollama_url": self._ollama_url,
            "models": model_status,
        }

    async def list_ollama_models(self) -> list[dict[str, Any]]:
        """List models available in Ollama."""
        try:
            resp = await self._client.get(f"{self._ollama_url}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            return data.get("models", [])
        except Exception as e:
            logger.warning("Failed to list Ollama models: %s", e)
            return []

    async def _ollama_pull(self, model: LocalModel) -> dict[str, Any]:
        """Pull and load a model via Ollama."""
        try:
            resp = await self._client.post(
                f"{self._ollama_url}/api/pull",
                json={"name": model.model_path, "stream": False},
                timeout=600,
            )
            resp.raise_for_status()
            self._loaded.add(model.name)
            return {"status": "loaded", "model": model.name, "runtime": "ollama"}
        except Exception as e:
            logger.error("Ollama pull failed for %s: %s", model.name, e)
            return {"error": str(e)}

    async def _check_ollama(self) -> bool:
        """Check if Ollama is running."""
        try:
            resp = await self._client.get(f"{self._ollama_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        await self._client.aclose()
