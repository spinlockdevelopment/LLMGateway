"""
Web UI routes and action endpoints for the LLM Gateway dashboard.

Routes:
    GET  /               — HTML dashboard (single-page app)
    POST /ui/config/save — save config from editor
    POST /ui/config/validate — validate YAML without saving
    POST /ui/config/reset — reset to defaults
    POST /ui/services/{name}/start — start a service
    POST /ui/services/{name}/stop — stop a service
    POST /ui/services/{name}/restart — restart a service
    POST /ui/ollama/pull — pull an Ollama model
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

log = logging.getLogger("llm-gateway")

_DASHBOARD_PATH = Path(__file__).parent / "dashboard.html"


def create_ui_router() -> APIRouter:
    router = APIRouter()

    # ── Dashboard page ────────────────────────────────────────────────────────

    @router.get("/", response_class=HTMLResponse)
    async def dashboard():
        """Serve the single-page dashboard."""
        try:
            html = _DASHBOARD_PATH.read_text(encoding="utf-8")
            return HTMLResponse(content=html)
        except FileNotFoundError:
            return HTMLResponse(
                content="<h1>Dashboard not found</h1><p>dashboard.html is missing.</p>",
                status_code=500,
            )

    # ── Config actions ────────────────────────────────────────────────────────

    @router.post("/ui/config/save")
    async def save_config(request: Request):
        """Save config from the YAML editor."""
        body = await request.json()
        yaml_text = body.get("yaml", "")
        if not yaml_text.strip():
            return JSONResponse(
                status_code=400,
                content={"errors": ["Empty config"], "warnings": []},
            )

        cm = request.app.state.config_manager
        errors, warnings = cm.save_raw_yaml(yaml_text)
        if errors:
            return JSONResponse(
                status_code=400,
                content={"errors": errors, "warnings": warnings},
            )
        return {"status": "saved", "warnings": warnings}

    @router.post("/ui/config/validate")
    async def validate_config(request: Request):
        """Validate YAML without saving."""
        body = await request.json()
        yaml_text = body.get("yaml", "")

        import yaml as pyyaml
        try:
            parsed = pyyaml.safe_load(yaml_text)
        except pyyaml.YAMLError as e:
            return JSONResponse(
                status_code=400,
                content={"valid": False, "errors": [f"YAML syntax error: {e}"], "warnings": []},
            )

        if not isinstance(parsed, dict):
            return JSONResponse(
                status_code=400,
                content={"valid": False, "errors": ["Config must be a YAML mapping"], "warnings": []},
            )

        from config.schema import validate_config as validate
        errors, warnings = validate(parsed)
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    @router.post("/ui/config/reset")
    async def reset_config(request: Request):
        """Reset config to shipped defaults."""
        cm = request.app.state.config_manager
        cm.reset_to_defaults()
        return {"status": "reset", "yaml": cm.get_yaml_text()}

    @router.get("/ui/config/yaml")
    async def get_config_yaml(request: Request):
        """Get the current config as raw YAML text (for the editor)."""
        cm = request.app.state.config_manager
        return {"yaml": cm.get_yaml_text()}

    # ── Service actions ───────────────────────────────────────────────────────

    @router.post("/ui/services/{name}/start")
    async def start_service(name: str, request: Request):
        """Start a managed service."""
        svc = request.app.state.service_registry.get(name)
        if svc is None:
            raise HTTPException(404, f"Service not found: {name}")
        ok = await svc.start()
        return {"status": "started" if ok else "failed", "service": svc.status().to_dict()}

    @router.post("/ui/services/{name}/stop")
    async def stop_service(name: str, request: Request):
        """Stop a managed service."""
        svc = request.app.state.service_registry.get(name)
        if svc is None:
            raise HTTPException(404, f"Service not found: {name}")
        ok = await svc.stop()
        return {"status": "stopped" if ok else "failed", "service": svc.status().to_dict()}

    @router.post("/ui/services/{name}/restart")
    async def restart_service(name: str, request: Request):
        """Restart a managed service."""
        svc = request.app.state.service_registry.get(name)
        if svc is None:
            raise HTTPException(404, f"Service not found: {name}")
        ok = await svc.restart()
        return {"status": "restarted" if ok else "failed", "service": svc.status().to_dict()}

    # ── Ollama model management ───────────────────────────────────────────────

    @router.post("/ui/ollama/pull")
    async def pull_ollama_model(request: Request):
        """Pull a model via Ollama."""
        body = await request.json()
        model_name = body.get("model", "").strip()
        if not model_name:
            return JSONResponse(status_code=400, content={"error": "Model name is required"})

        registry = request.app.state.service_registry
        ollama = registry.get("ollama")
        if ollama is None:
            return JSONResponse(status_code=404, content={"error": "Ollama service not configured"})

        from services.ollama import OllamaService
        if not isinstance(ollama, OllamaService):
            return JSONResponse(status_code=400, content={"error": "Service is not an Ollama instance"})

        ok, output = await ollama.pull_model(model_name)
        return {
            "status": "success" if ok else "failed",
            "model": model_name,
            "output": output[:2000],
        }

    @router.get("/ui/ollama/models")
    async def list_ollama_models(request: Request):
        """List models available in Ollama."""
        registry = request.app.state.service_registry
        ollama = registry.get("ollama")
        if ollama is None:
            return {"models": []}

        from services.ollama import OllamaService
        if not isinstance(ollama, OllamaService):
            return {"models": []}

        models = await ollama.list_models()
        return {"models": models}

    return router
