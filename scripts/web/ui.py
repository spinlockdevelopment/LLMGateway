"""
Web UI routes and action endpoints for the LLM Gateway dashboard.

Routes:
    GET  /               — HTML dashboard (single-page app)
    POST /ui/config/save — save config from editor
    POST /ui/config/validate — validate YAML without saving
    POST /ui/config/reset — reset to defaults
    GET  /ui/secrets/example — keys and default values from .env.example
    GET  /ui/secrets — current .env entries (or defaults)
    POST /ui/secrets/save — save .env (backup if exists; restarts LiteLLM if relevant keys changed)
    POST /ui/models/pull — pull a model via Docker Model Runner
    DELETE /ui/models/{name:path} — remove a model via Docker Model Runner
    POST /ui/whisper/start — start the Whisper service
    POST /ui/whisper/stop — stop the Whisper service
    POST /ui/whisper/restart — restart the Whisper service
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from datetime import datetime
from pathlib import Path

from urllib.parse import unquote

import json as _json

import httpx
from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

log = logging.getLogger("llm-gateway")

_EXCLUDED_ENV_KEYS = frozenset({"DATABASE_URL"})
_ENV_BACKUP_SUFFIX = ".bak"
_ENV_MAX_BACKUPS = 5

# Base URL (and Azure version) vars are only written when the associated API key is set.
_BASE_URL_OR_VERSION_TO_API_KEY = {
    "OPENROUTER_API_BASE": "OPENROUTER_API_KEY",
    "ANTHROPIC_API_BASE": "ANTHROPIC_API_KEY",
    "OPENAI_BASE_URL": "OPENAI_API_KEY",
    "GEMINI_API_BASE": "GEMINI_API_KEY",
    "XAI_API_BASE": "XAI_API_KEY",
    "AZURE_API_BASE": "AZURE_API_KEY",
    "AZURE_API_VERSION": "AZURE_API_KEY",
}

# Keys in .env that affect LiteLLM — changes to any of these require a container restart.
_LITELLM_ENV_KEYS = frozenset({
    "LITELLM_MASTER_KEY",
    "OPENROUTER_API_KEY", "OPENROUTER_API_BASE",
    "ANTHROPIC_API_KEY", "ANTHROPIC_API_BASE",
    "OPENAI_API_KEY", "OPENAI_BASE_URL",
    "GEMINI_API_KEY", "GEMINI_API_BASE",
    "XAI_API_KEY", "XAI_API_BASE",
    "AZURE_API_KEY", "AZURE_API_BASE", "AZURE_API_VERSION",
    "PERPLEXITY_API_KEY",
    "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
    "LITELLM_SALT_KEY",
})

# Strong references to fire-and-forget background tasks to prevent GC collection.
_background_tasks: set[asyncio.Task] = set()

_DASHBOARD_PATH = Path(__file__).parent / "dashboard.html"


async def _restart_litellm_container(repo_dir: Path, data_dir: Path | None = None) -> bool:
    """
    Restart the litellm Docker Compose service so it picks up .env changes.

    Best-effort: logs warnings on failure but never raises.
    Returns True if the restart command succeeded.
    """
    compose_file = repo_dir / "docker" / "docker-compose.yml"
    if not compose_file.exists():
        log.warning("  docker-compose.yml not found — skipping LiteLLM restart")
        return False

    # Build command with --env-file pointing to data_dir/.env
    cmd = ["docker", "compose", "-f", str(compose_file)]
    env_file = (data_dir or repo_dir) / ".env"
    if env_file.exists():
        cmd.extend(["--env-file", str(env_file)])
    cmd.extend(["restart", "litellm"])

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        if proc.returncode == 0:
            log.info("  LiteLLM container restarted after .env change")
            return True
        else:
            err = (stderr or stdout or b"").decode(errors="replace").strip()
            log.warning("  LiteLLM restart failed (rc=%d): %s", proc.returncode, err)
            return False
    except asyncio.TimeoutError:
        log.warning("  LiteLLM restart timed out (60s)")
        return False
    except FileNotFoundError:
        log.warning("  docker command not found — cannot restart LiteLLM")
        return False
    except Exception:
        log.warning("  LiteLLM restart failed unexpectedly", exc_info=True)
        return False


def _litellm_keys_changed(old_entries: list[dict], new_entries: list[dict]) -> bool:
    """
    Compare old and new .env entries to determine if any LiteLLM-relevant
    keys have changed (added, removed, or modified).
    """
    old_map = {e["key"]: e["value"] for e in old_entries if e["key"] in _LITELLM_ENV_KEYS}
    new_map = {e["key"]: e["value"] for e in new_entries if e["key"] in _LITELLM_ENV_KEYS}
    return old_map != new_map


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

    # ── Secrets (.env) helpers ────────────────────────────────────────────────

    def _env_paths(request: Request):
        repo_dir = getattr(request.app.state, "repo_dir", None)
        data_dir = getattr(request.app.state, "data_dir", None) or repo_dir
        if repo_dir is None:
            raise HTTPException(500, "Repository path not configured")
        # .env lives in data_dir; .env.example stays in repo
        return data_dir / ".env", repo_dir / ".env.example"

    def _iter_env_entries(path: Path):
        """Yield (key, value) pairs from a .env-style file, skipping comments and excluded keys."""
        if not path.exists():
            return
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, rest = line.partition("=")
            key = key.strip()
            if key in _EXCLUDED_ENV_KEYS:
                continue
            yield key, rest.strip()

    def _parse_env_file(path: Path) -> list[dict]:
        """Parse a .env file into list of {key, value}."""
        return [{"key": k, "value": v} for k, v in _iter_env_entries(path)]

    def _parse_env_example(path: Path) -> dict[str, str]:
        """Parse .env.example into key -> default value."""
        return dict(_iter_env_entries(path))

    def _create_env_backup(env_path: Path) -> None:
        """Create a timestamped backup of .env and prune old backups."""
        if not env_path.exists():
            return
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = env_path.parent / f".env.{timestamp}{_ENV_BACKUP_SUFFIX}"
        shutil.copy2(env_path, backup)
        log.debug("Env backup created: %s", backup)
        backups = sorted(env_path.parent.glob(f".env.*{_ENV_BACKUP_SUFFIX}"), reverse=True)
        for old in backups[_ENV_MAX_BACKUPS:]:
            old.unlink(missing_ok=True)

    # ── Secrets routes ────────────────────────────────────────────────────────

    @router.get("/ui/secrets/example")
    async def get_secrets_example(request: Request):
        """Return keys and default values from .env.example (excluding DATABASE_URL)."""
        _env_path, example_path = _env_paths(request)
        defaults = _parse_env_example(example_path)
        return {"defaults": defaults, "availableKeys": sorted(defaults.keys())}

    @router.get("/ui/secrets")
    async def get_secrets(request: Request):
        """Return current .env entries. If .env exists use it; else use defaults from .env.example."""
        env_path, example_path = _env_paths(request)
        defaults = _parse_env_example(example_path)
        if env_path.exists():
            entries = _parse_env_file(env_path)
            for e in entries:
                if e["key"] not in defaults:
                    defaults[e["key"]] = ""
            for key in defaults:
                if not any(e["key"] == key for e in entries):
                    entries.append({"key": key, "value": defaults[key]})
            entries.sort(key=lambda x: x["key"])
            return {"entries": entries, "defaults": defaults}
        entries = [{"key": k, "value": v} for k, v in sorted(defaults.items())]
        return {"entries": entries, "defaults": defaults}

    @router.post("/ui/secrets/save")
    async def save_secrets(request: Request):
        """Save .env from key-value list. Backs up existing .env. Blank values omitted. Base URL vars only written when their associated API key is set. DATABASE_URL is never written. Automatically restarts the LiteLLM container if any LiteLLM-relevant keys changed."""
        body = await request.json()
        entries = body.get("entries", [])
        if not isinstance(entries, list):
            return JSONResponse(status_code=400, content={"error": "entries must be an array"})

        env_path, _ = _env_paths(request)

        # Snapshot current .env entries before overwriting (for change detection)
        old_entries = _parse_env_file(env_path)

        _create_env_backup(env_path)

        keys_to_value = {}
        order = []
        for item in entries:
            k = (item.get("key") or "").strip()
            v = (item.get("value") or "").strip()
            if not k or k in _EXCLUDED_ENV_KEYS or "=" in k or "\n" in k:
                continue
            keys_to_value[k] = v
            if k not in order:
                order.append(k)

        lines = []
        for key in order:
            value = keys_to_value[key]
            if not value:
                continue
            if key in _BASE_URL_OR_VERSION_TO_API_KEY:
                api_key_var = _BASE_URL_OR_VERSION_TO_API_KEY[key]
                if not keys_to_value.get(api_key_var, "").strip():
                    continue
            lines.append(f"{key}={value}")

        try:
            env_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        except OSError as e:
            log.exception("Failed to write .env")
            return JSONResponse(status_code=500, content={"error": str(e)})

        # Detect if any LiteLLM-relevant env vars changed and restart if needed
        new_entries = _parse_env_file(env_path)
        litellm_restarting = False
        if _litellm_keys_changed(old_entries, new_entries):
            repo_dir = getattr(request.app.state, "repo_dir", None)
            data_dir = getattr(request.app.state, "data_dir", None)
            if repo_dir is not None:
                log.info("  LiteLLM-relevant env vars changed — restarting container...")
                task = asyncio.create_task(_restart_litellm_container(repo_dir, data_dir))
                _background_tasks.add(task)
                task.add_done_callback(_background_tasks.discard)
                litellm_restarting = True

        return {"status": "saved", "litellm_restarting": litellm_restarting}

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

    # ── DMR model management ──────────────────────────────────────────────────

    @router.post("/ui/models/pull")
    async def pull_model(request: Request):
        """Pull a model via Docker Model Runner."""
        body = await request.json()
        model_name = (body.get("model") or "").strip()
        if not model_name:
            return JSONResponse(status_code=400, content={"error": "Model name is required"})

        dmr = request.app.state.dmr
        ok, output = await dmr.pull_model(model_name)
        return {
            "status": "success" if ok else "failed",
            "model": model_name,
            "output": output[:2000] if output else "",
        }

    @router.get("/ui/models/pull/stream")
    async def pull_model_stream(model: str, request: Request):
        """Stream model pull progress via Server-Sent Events."""
        model_name = model.strip()
        if not model_name:
            return JSONResponse(status_code=400, content={"error": "Model name is required"})

        dmr = request.app.state.dmr

        async def event_stream():
            async for line, done, success in dmr.pull_model_stream(model_name):
                payload = _json.dumps({"line": line, "done": done, "success": success})
                yield f"data: {payload}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @router.delete("/ui/models/{name:path}")
    async def remove_model(name: str, request: Request):
        """Remove a model via Docker Model Runner."""
        model_name = unquote(name)
        dmr = request.app.state.dmr
        ok = await dmr.remove_model(model_name)
        return {"status": "removed" if ok else "failed", "model": model_name}

    # ── Whisper actions ───────────────────────────────────────────────────────

    @router.post("/ui/whisper/start")
    async def whisper_start(request: Request):
        """Start the Whisper service."""
        whisper = request.app.state.whisper
        ok = await whisper.start()
        return {"status": "started" if ok else "failed", **whisper.status_dict()}

    @router.post("/ui/whisper/stop")
    async def whisper_stop(request: Request):
        """Stop the Whisper service."""
        whisper = request.app.state.whisper
        ok = await whisper.stop()
        return {"status": "stopped" if ok else "failed", **whisper.status_dict()}

    @router.post("/ui/whisper/restart")
    async def whisper_restart(request: Request):
        """Restart the Whisper service."""
        whisper = request.app.state.whisper
        ok = await whisper.restart()
        return {"status": "restarted" if ok else "failed", **whisper.status_dict()}

    @router.post("/ui/whisper/transcribe")
    async def whisper_transcribe(request: Request, file: UploadFile = File(...)):
        """Upload an audio file and proxy to the Whisper server for transcription."""
        whisper = request.app.state.whisper
        if whisper.state != "running":
            return JSONResponse(status_code=400, content={"error": "Whisper is not running"})

        health_url = whisper.health_url
        if not health_url:
            return JSONResponse(status_code=400, content={"error": "Whisper health URL not configured"})

        # Derive transcription URL from health URL (e.g. http://localhost:8178/health -> .../v1/audio/transcriptions)
        base_url = health_url.rsplit("/health", 1)[0]
        transcription_url = f"{base_url}/v1/audio/transcriptions"

        content = await file.read()
        if len(content) > 25 * 1024 * 1024:
            return JSONResponse(status_code=413, content={"error": "File too large (max 25 MB)"})

        filename = Path(file.filename).name if file.filename else "audio.wav"
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    transcription_url,
                    files={"file": (filename, content, file.content_type or "audio/wav")},
                    data={"model": "whisper-1"},
                )
                resp.raise_for_status()
                return {"status": "ok", "text": resp.json().get("text", "")}
        except httpx.TimeoutException:
            return JSONResponse(status_code=504, content={"error": "Transcription timed out"})
        except Exception as e:
            log.warning("Whisper transcription failed: %s", e)
            return JSONResponse(status_code=502, content={"error": f"Transcription failed: {e}"})

    return router
