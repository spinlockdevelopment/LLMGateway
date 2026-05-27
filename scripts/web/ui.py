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
    POST /ui/services/{name}/start — start a service
    POST /ui/services/{name}/stop — stop a service
    POST /ui/services/{name}/restart — restart a service
    GET  /ui/dmr/models — list models pulled to Docker Model Runner
    POST /ui/dmr/pull — pull a model via `docker model pull` (blocking)
    GET  /ui/dmr/pull/stream?model=X — same pull, streamed as SSE
    GET  /ui/dmr/llmfit/status — is llmfit installed; version
    GET  /ui/dmr/llmfit/recommend — hardware-matched model recommendations
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
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

# Web-search providers managed via .env. When the dashboard saves a non-empty
# value for one of these env vars, the corresponding search_tools entry is
# auto-added to litellm-config.yaml (idempotent — existing entries are left
# alone). Clearing the key does not remove the entry; users can drop it
# manually from the Config tab if they want.
_SEARCH_PROVIDERS: dict[str, tuple[str, str]] = {
    # env var → (search_tool_name, search_provider)
    "TAVILY_API_KEY": ("tavily-search", "tavily"),
    "EXA_API_KEY": ("exa-search", "exa_ai"),
    "BRAVE_SEARCH_API_KEY": ("brave-search", "brave"),
    "SERPER_API_KEY": ("serper-search", "serper"),
}


def _build_search_tool_block(env_key: str, tool_name: str, provider: str) -> str:
    """Render one search_tools list entry as YAML text (leading newline, 2-space indent)."""
    return (
        f"\n  - search_tool_name: {tool_name}\n"
        f"    litellm_params:\n"
        f"      search_provider: {provider}\n"
        f"      api_key: os.environ/{env_key}\n"
    )


def _existing_search_tool_env_keys(yaml_text: str) -> set[str]:
    """Set of env var names already referenced by search_tools[*].litellm_params.api_key."""
    import yaml as pyyaml
    try:
        parsed = pyyaml.safe_load(yaml_text) or {}
    except pyyaml.YAMLError:
        return set()
    tools = parsed.get("search_tools") or []
    env_keys: set[str] = set()
    for entry in tools:
        if not isinstance(entry, dict):
            continue
        params = entry.get("litellm_params") or {}
        api_key = params.get("api_key", "")
        if isinstance(api_key, str) and api_key.startswith("os.environ/"):
            env_keys.add(api_key.split("/", 1)[1])
    return env_keys


def _present_env_keys(env_path: Path) -> set[str]:
    """Parse a .env file and return keys whose value is non-empty."""
    if not env_path.exists():
        return set()
    keys: set[str] = set()
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        if val.strip():
            keys.add(key.strip())
    return keys


def sync_search_tools_with_env(repo_dir: Path, data_dir: Path) -> list[str]:
    """
    Idempotent sync: for each web-search env var present in .env, ensure the
    matching search_tools entry exists in litellm-config.yaml. Returns the
    list of tool_names that were added (empty if nothing changed or no env).

    Caller decides whether to restart the LiteLLM container.
    """
    env_path = data_dir / ".env"
    present = _present_env_keys(env_path) & _SEARCH_PROVIDERS.keys()
    if not present:
        return []

    data_cfg = data_dir / "litellm-config.yaml"
    repo_cfg = repo_dir / "config" / "litellm-config.yaml"
    if data_cfg.exists():
        cfg_text = data_cfg.read_text(encoding="utf-8")
    elif repo_cfg.exists():
        cfg_text = repo_cfg.read_text(encoding="utf-8")
    else:
        return []

    already = _existing_search_tool_env_keys(cfg_text)
    to_add: list[tuple[str, str, str]] = []
    for env_key in sorted(present):
        if env_key in already:
            continue
        tool_name, provider = _SEARCH_PROVIDERS[env_key]
        to_add.append((env_key, tool_name, provider))

    if not to_add:
        return []

    new_text = _insert_search_tool_entries(cfg_text, to_add)
    try:
        if data_cfg.exists():
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            shutil.copy2(data_cfg, data_cfg.parent / f"litellm-config.{ts}.yaml.bak")
        data_cfg.parent.mkdir(parents=True, exist_ok=True)
        data_cfg.write_text(new_text, encoding="utf-8")
        repo_cfg.parent.mkdir(parents=True, exist_ok=True)
        repo_cfg.write_text(new_text, encoding="utf-8")
    except OSError:
        log.warning(
            "  Failed to write litellm-config.yaml during search-tools sync",
            exc_info=True,
        )
        return []

    return [tn for _, tn, _ in to_add]


def _insert_search_tool_entries(yaml_text: str, entries: list[tuple[str, str, str]]) -> str:
    """
    Append entries (env_key, tool_name, provider) to the existing search_tools
    block. Preserves comments and trailing top-level sections. If no
    search_tools section exists yet, appends a new one at the end of the file.
    """
    if not entries:
        return yaml_text

    addition = "".join(
        _build_search_tool_block(env_key, tool_name, provider)
        for env_key, tool_name, provider in entries
    )

    m = re.search(r"(^search_tools:[ \t]*\n)", yaml_text, re.MULTILINE)
    if not m:
        sep = "" if yaml_text.endswith("\n") else "\n"
        return yaml_text + sep + "\nsearch_tools:" + addition

    # Find the end of the search_tools block — the next top-level (column-0
    # non-whitespace) line, or EOF. Blank/comment lines are part of the block.
    section_start = m.end()
    rest = yaml_text[section_start:]
    end_match = re.search(r"^(?=[^\s#])", rest, re.MULTILINE)
    block_end = section_start + end_match.start() if end_match else len(yaml_text)

    before = yaml_text[:section_start]
    block = yaml_text[section_start:block_end]
    after = yaml_text[block_end:]

    # Preserve trailing blank lines after the block (they separate it from the
    # next section visually).
    block_lines = block.splitlines(keepends=True)
    trailing_blanks: list[str] = []
    while block_lines and not block_lines[-1].strip():
        trailing_blanks.insert(0, block_lines.pop())

    return before + "".join(block_lines) + addition + "".join(trailing_blanks) + after


# Keys in .env that affect LiteLLM — changes to any of these require a container restart.
_LITELLM_ENV_KEYS = frozenset({
    "LITELLM_MASTER_KEY",
    "LITELLM_SALT_KEY",
    # LLM provider auth
    "OPENROUTER_API_KEY", "OPENROUTER_API_BASE",
    "ANTHROPIC_API_KEY", "ANTHROPIC_API_BASE",
    "OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_ORGANIZATION",
    "GEMINI_API_KEY", "GEMINI_API_BASE",
    "XAI_API_KEY", "XAI_API_BASE",
    "AZURE_API_KEY", "AZURE_API_BASE", "AZURE_API_VERSION",
    "PERPLEXITY_API_KEY",
    "DEEPSEEK_API_KEY", "MISTRAL_API_KEY", "TOGETHER_API_KEY",
    "COHERE_API_KEY", "FIREWORKS_API_KEY", "REPLICATE_API_KEY",
    # Web-search providers (consumed by websearch_interception callback)
    "TAVILY_API_KEY", "EXA_API_KEY",
    "BRAVE_SEARCH_API_KEY", "SERPER_API_KEY",
    # OAuth + SSO
    "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
    "OAUTH_TOKEN_INFO_ENDPOINT",
    "OAUTH_USER_ID_FIELD_NAME", "OAUTH_USER_ROLE_FIELD_NAME", "OAUTH_USER_TEAM_ID_FIELD_NAME",
    # Logging callbacks
    "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST",
    "HELICONE_API_KEY",
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

    def _parse_env_file(path: Path) -> list[dict]:
        """Parse a .env file into list of {key, value}. Skips comments and empty lines."""
        if not path.exists():
            return []
        entries = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, rest = line.partition("=")
            key = key.strip()
            if key in _EXCLUDED_ENV_KEYS:
                continue
            value = rest.strip()
            entries.append({"key": key, "value": value})
        return entries

    def _parse_env_example(path: Path) -> dict[str, str]:
        """Parse .env.example into key -> default value. Excludes DATABASE_URL."""
        if not path.exists():
            return {}
        defaults = {}
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, rest = line.partition("=")
            key = key.strip()
            if key in _EXCLUDED_ENV_KEYS:
                continue
            defaults[key] = rest.strip()
        return defaults

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

        # Auto-add search_tools entries for any web-search API key that now has
        # a value but isn't yet wired up in litellm-config.yaml. Idempotent.
        repo_dir = getattr(request.app.state, "repo_dir", None)
        data_dir = getattr(request.app.state, "data_dir", None) or repo_dir
        search_tools_added: list[str] = []
        if repo_dir is not None and data_dir is not None:
            search_tools_added = sync_search_tools_with_env(repo_dir, data_dir)
            if search_tools_added:
                log.info("  Auto-added search_tools: %s", search_tools_added)

        # Detect if any LiteLLM-relevant env vars changed and restart if needed.
        # A search_tools edit also requires a restart even if the env keys
        # themselves are unchanged (rare — would only happen if the user
        # somehow saved without touching the search keys but the config file
        # is missing entries).
        new_entries = _parse_env_file(env_path)
        litellm_restarting = False
        if _litellm_keys_changed(old_entries, new_entries) or search_tools_added:
            if repo_dir is not None:
                log.info("  LiteLLM-relevant env vars changed — restarting container...")
                task = asyncio.create_task(_restart_litellm_container(repo_dir, data_dir))
                _background_tasks.add(task)
                task.add_done_callback(_background_tasks.discard)
                litellm_restarting = True

        return {
            "status": "saved",
            "litellm_restarting": litellm_restarting,
            "search_tools_added": search_tools_added,
        }

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

    # ── LiteLLM config (litellm-config.yaml) ──────────────────────────────────
    # Edits the file mounted into the litellm Docker container. The data_dir
    # copy is the source of truth at runtime; on save we also overwrite the
    # repo copy that docker-compose actually mounts, then restart the container.

    def _litellm_cfg_paths(request: Request) -> tuple[Path, Path]:
        repo_dir = getattr(request.app.state, "repo_dir", None)
        data_dir = getattr(request.app.state, "data_dir", None) or repo_dir
        if repo_dir is None:
            raise HTTPException(500, "Repository path not configured")
        return data_dir / "litellm-config.yaml", repo_dir / "config" / "litellm-config.yaml"

    def _read_litellm_yaml(request: Request) -> str:
        data_cfg, repo_cfg = _litellm_cfg_paths(request)
        if data_cfg.exists():
            return data_cfg.read_text(encoding="utf-8")
        if repo_cfg.exists():
            return repo_cfg.read_text(encoding="utf-8")
        return ""

    def _validate_litellm_yaml(yaml_text: str) -> tuple[list[str], list[str], dict | None]:
        import yaml as pyyaml
        try:
            parsed = pyyaml.safe_load(yaml_text)
        except pyyaml.YAMLError as e:
            return [f"YAML syntax error: {e}"], [], None
        if not isinstance(parsed, dict):
            return ["Config must be a YAML mapping"], [], None
        warnings: list[str] = []
        ml = parsed.get("model_list")
        if ml is None:
            warnings.append("model_list is missing — LiteLLM will start with no models")
        elif not isinstance(ml, list):
            return ["model_list must be a list"], warnings, None
        return [], warnings, parsed

    @router.get("/ui/litellm-config/yaml")
    async def get_litellm_config_yaml(request: Request):
        return {"yaml": _read_litellm_yaml(request)}

    @router.post("/ui/litellm-config/validate")
    async def validate_litellm_config(request: Request):
        body = await request.json()
        errors, warnings, _ = _validate_litellm_yaml(body.get("yaml", ""))
        return {"valid": not errors, "errors": errors, "warnings": warnings}

    @router.post("/ui/litellm-config/save")
    async def save_litellm_config(request: Request):
        body = await request.json()
        yaml_text = body.get("yaml", "")
        if not yaml_text.strip():
            return JSONResponse(
                status_code=400,
                content={"errors": ["Empty config"], "warnings": []},
            )
        errors, warnings, _ = _validate_litellm_yaml(yaml_text)
        if errors:
            return JSONResponse(status_code=400, content={"errors": errors, "warnings": warnings})

        data_cfg, repo_cfg = _litellm_cfg_paths(request)

        if data_cfg.exists():
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = data_cfg.parent / f"litellm-config.{timestamp}.yaml.bak"
            try:
                shutil.copy2(data_cfg, backup)
            except OSError:
                log.warning("  Could not back up litellm-config.yaml", exc_info=True)

        try:
            data_cfg.parent.mkdir(parents=True, exist_ok=True)
            data_cfg.write_text(yaml_text, encoding="utf-8")
            repo_cfg.parent.mkdir(parents=True, exist_ok=True)
            repo_cfg.write_text(yaml_text, encoding="utf-8")
        except OSError as e:
            log.exception("Failed to write litellm-config.yaml")
            return JSONResponse(status_code=500, content={"errors": [str(e)], "warnings": warnings})

        repo_dir = getattr(request.app.state, "repo_dir", None)
        data_dir = getattr(request.app.state, "data_dir", None)
        litellm_restarting = False
        if repo_dir is not None:
            log.info("  LiteLLM config edited — restarting container...")
            task = asyncio.create_task(_restart_litellm_container(repo_dir, data_dir))
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)
            litellm_restarting = True

        return {"status": "saved", "warnings": warnings, "litellm_restarting": litellm_restarting}

    # ── Service actions ───────────────────────────────────────────────────────

    @router.post("/ui/services/{name}/start")
    async def start_service(name: str, request: Request):
        """Start a managed service asynchronously. Auto-stops mutex-group siblings."""
        from services import ServiceState

        registry = request.app.state.service_registry
        svc = registry.get(name)
        if svc is None:
            raise HTTPException(404, f"Service not found: {name}")

        active = (ServiceState.RUNNING, ServiceState.STARTING, ServiceState.UNHEALTHY)
        swapped = [s.name for s in registry.siblings_in_group(name) if s.state in active]

        task = asyncio.create_task(registry.start_with_mutex(name))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

        # Return immediately; clients should poll /api/services for updated state.
        return {
            "status": "starting",
            "service": svc.status().to_dict(),
            "swapped_out": swapped,
        }

    @router.post("/ui/services/{name}/stop")
    async def stop_service(name: str, request: Request):
        """Stop a managed service asynchronously."""
        svc = request.app.state.service_registry.get(name)
        if svc is None:
            raise HTTPException(404, f"Service not found: {name}")

        task = asyncio.create_task(svc.stop())
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

        return {"status": "stopping", "service": svc.status().to_dict()}

    @router.post("/ui/services/{name}/restart")
    async def restart_service(name: str, request: Request):
        """Restart a managed service asynchronously."""
        svc = request.app.state.service_registry.get(name)
        if svc is None:
            raise HTTPException(404, f"Service not found: {name}")

        async def _restart():
            await svc.restart()

        task = asyncio.create_task(_restart())
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

        return {"status": "restarting", "service": svc.status().to_dict()}

    def _set_service_enabled_in_yaml(cm, name: str, enabled: bool) -> None:
        """Write services.{name}.enabled into the user YAML override.

        Reads the user file directly (not the merged config) so we only
        persist a single key — letting future changes in the shipped
        defaults flow through without being frozen into the override.
        """
        import yaml as pyyaml
        user_path = cm.user_path
        if user_path.exists():
            try:
                data = pyyaml.safe_load(user_path.read_text(encoding="utf-8")) or {}
            except Exception:
                data = {}
        else:
            data = {}
        services = data.setdefault("services", {})
        slot = services.setdefault(name, {})
        slot["enabled"] = enabled
        user_path.parent.mkdir(parents=True, exist_ok=True)
        user_path.write_text(
            pyyaml.dump(data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
        try:
            import os as _os
            _os.chmod(user_path, 0o600)
        except OSError:
            pass

    @router.post("/ui/services/{name}/enable")
    async def enable_service(name: str, request: Request):
        """Flip a service's `enabled: true` flag, then start it.

        If the service has a `mutex_group` (e.g. whisper-fast/whisper-large
        share 'whisper'), siblings in the same group are persisted as
        `enabled: false` and stopped first — matches what
        registry.start_with_mutex would do at runtime, but persists the
        choice so the next management restart still respects it.
        """
        from services import ServiceState
        registry = request.app.state.service_registry
        cm = request.app.state.config_manager
        svc = registry.get(name)
        if svc is None:
            raise HTTPException(404, "unknown service")

        # Persist mutex sibling disable + this service's enable.
        for sib in registry.siblings_in_group(name):
            if sib.enabled:
                _set_service_enabled_in_yaml(cm, sib.name, False)
                sib.svc_config["enabled"] = False
                if sib.state not in (ServiceState.STOPPED, ServiceState.DISABLED):
                    try:
                        await sib.stop()
                    except Exception:
                        log.warning("Failed to stop mutex sibling %s", sib.name, exc_info=True)
                sib._state = ServiceState.DISABLED

        _set_service_enabled_in_yaml(cm, name, True)
        svc.svc_config["enabled"] = True
        if svc.state == ServiceState.DISABLED:
            svc._state = ServiceState.STOPPED

        ok = await registry.start_with_mutex(name)
        return {
            "status": "enabled" if ok else "enable_failed",
            "service": svc.status().to_dict() if hasattr(svc, "status") else None,
        }

    @router.post("/ui/services/{name}/disable")
    async def disable_service(name: str, request: Request):
        """Stop the service if running, then persist `enabled: false`."""
        from services import ServiceState
        registry = request.app.state.service_registry
        cm = request.app.state.config_manager
        svc = registry.get(name)
        if svc is None:
            raise HTTPException(404, "unknown service")

        if svc.state not in (ServiceState.STOPPED, ServiceState.DISABLED):
            try:
                await svc.stop()
            except Exception:
                log.warning("Failed to stop %s during disable", name, exc_info=True)

        _set_service_enabled_in_yaml(cm, name, False)
        svc.svc_config["enabled"] = False
        svc._state = ServiceState.DISABLED
        return {"status": "disabled"}

    @router.get("/ui/services/{name}/logs")
    async def service_logs(name: str, request: Request):
        """
        Return the tail of a service's log file from the gateway data_dir/logs.

        Query params:
            lines: number of lines from the end of the log (default 200).
        """
        from data_dir import log_dir as gateway_log_dir

        lines_param = request.query_params.get("lines")
        try:
            max_lines = int(lines_param) if lines_param is not None else 200
        except ValueError:
            max_lines = 200
        max_lines = max(1, min(max_lines, 2000))

        log_path = gateway_log_dir() / f"{name}.log"
        if not log_path.exists():
            return {"lines": [], "truncated": False, "message": "No logs available for this service yet."}

        def _tail(path: Path, num_lines: int) -> tuple[list[str], bool]:
            # Simple tail implementation; efficient for reasonably sized logs.
            with path.open("rb") as f:
                f.seek(0, 2)
                size = f.tell()
                block_size = 4096
                data = b""
                pos = size
                while pos > 0 and data.count(b"\n") <= num_lines:
                    read_size = min(block_size, pos)
                    pos -= read_size
                    f.seek(pos)
                    data = f.read(read_size) + data
                lines = data.splitlines()[-num_lines:]
                return [line.decode("utf-8", errors="replace") for line in lines], len(lines) == num_lines and size > len(data)

        log_lines, truncated = _tail(log_path, max_lines)
        return {"lines": log_lines, "truncated": truncated}

    # ── In-UI Logs panel ──────────────────────────────────────────────────────
    # The dashboard's Logs tab is the lean alternative to Grafana/Loki.
    # `/ui/logs/sources` lists what's available right now (so the panel can
    # build its source dropdown); `/ui/logs/{source}/tail` returns the last
    # N lines. Container sources go through `docker logs`; file sources tail
    # the gateway's own log files under data_dir/logs.

    _LOG_SOURCE_NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

    _CONTAINER_LOG_SOURCES = {
        # source_name : (container_name, human_label, group_name)
        "litellm":    ("llm-gateway",  "LiteLLM proxy",       "core"),
        "postgres":   ("llm-postgres", "PostgreSQL",          "core"),
        "open-webui": ("open-webui",   "Open WebUI",          "core"),
        "grafana":    ("grafana",      "Grafana",             "observability"),
        "prometheus": ("prometheus",   "Prometheus",          "observability"),
        "loki":       ("loki",         "Loki",                "observability"),
        "alloy":      ("alloy",        "Alloy",               "observability"),
    }

    _FILE_LOG_SOURCES = {
        # source_name : (filename_under_data_dir/logs, human_label, group_name)
        "management":     ("gateway.log",        "Management daemon", "host"),
        "llama-server":   ("llama-server.log",   "llama.cpp server",  "host"),
        "whisper-server": ("whisper-server.log", "whisper.cpp server","host"),
    }

    async def _container_exists(name: str) -> bool:
        if not shutil.which("docker"):
            return False
        try:
            rc, out, _ = await _run_cmd(
                ["docker", "ps", "-a", "--format", "{{.Names}}", "--filter", f"name=^{name}$"],
                timeout=5,
            )
        except (asyncio.TimeoutError, FileNotFoundError):
            return False
        return rc == 0 and name in {ln.strip() for ln in out.splitlines()}

    @router.get("/ui/logs/sources")
    async def log_sources(request: Request):
        """List log sources currently available, grouped for the UI selector.

        A source shows up only if its underlying data exists right now:
        containers must be present on the docker daemon, files must exist
        on disk. This keeps the dropdown free of dead entries.
        """
        sources: list[dict] = []

        for src, (container, label, group) in _CONTAINER_LOG_SOURCES.items():
            if await _container_exists(container):
                sources.append({
                    "id": src,
                    "label": label,
                    "kind": "container",
                    "group": group,
                })

        from data_dir import log_dir as gateway_log_dir
        log_root = gateway_log_dir()
        for src, (filename, label, group) in _FILE_LOG_SOURCES.items():
            path = log_root / filename
            if path.exists() and path.stat().st_size > 0:
                sources.append({
                    "id": src,
                    "label": label,
                    "kind": "file",
                    "group": group,
                })

        return {"sources": sources}

    @router.get("/ui/logs/{source}/tail")
    async def log_tail(source: str, request: Request):
        """Return the last N lines of a log source.

        Query params:
            lines: tail length (default 200, clamped to [1, 2000])
        """
        if not _LOG_SOURCE_NAME_RE.match(source):
            raise HTTPException(400, "invalid source name")

        lines_param = request.query_params.get("lines")
        try:
            max_lines = int(lines_param) if lines_param is not None else 200
        except ValueError:
            max_lines = 200
        max_lines = max(1, min(max_lines, 2000))

        # Container source: shell out to `docker logs --tail`.
        if source in _CONTAINER_LOG_SOURCES:
            container, _label, _group = _CONTAINER_LOG_SOURCES[source]
            if not shutil.which("docker"):
                return {"lines": [], "message": "docker CLI not found"}
            if not await _container_exists(container):
                return {
                    "lines": [],
                    "message": f"Container '{container}' is not present.",
                }
            try:
                rc, out, err = await _run_cmd(
                    ["docker", "logs", "--tail", str(max_lines), container],
                    timeout=15,
                )
            except asyncio.TimeoutError:
                return JSONResponse(status_code=504, content={"error": "docker logs timed out"})
            if rc != 0:
                return JSONResponse(
                    status_code=500,
                    content={"error": "docker logs failed", "stderr": err[:2000]},
                )
            # `docker logs` mixes stdout+stderr; either may be empty alone.
            combined = (out + err).splitlines()
            return {"lines": combined[-max_lines:], "source": source}

        # File source: tail the log file under data_dir/logs.
        if source in _FILE_LOG_SOURCES:
            from data_dir import log_dir as gateway_log_dir
            filename, _label, _group = _FILE_LOG_SOURCES[source]
            log_path = gateway_log_dir() / filename
            if not log_path.exists():
                return {"lines": [], "message": "No log file yet."}
            try:
                with log_path.open("rb") as f:
                    f.seek(0, 2)
                    size = f.tell()
                    block_size = 4096
                    data = b""
                    pos = size
                    while pos > 0 and data.count(b"\n") <= max_lines:
                        read_size = min(block_size, pos)
                        pos -= read_size
                        f.seek(pos)
                        data = f.read(read_size) + data
                    lines = data.splitlines()[-max_lines:]
            except OSError as e:
                return JSONResponse(status_code=500, content={"error": str(e)})
            return {
                "lines": [ln.decode("utf-8", errors="replace") for ln in lines],
                "source": source,
            }

        raise HTTPException(404, "unknown log source")

    # ── Docker compose stack actions ──────────────────────────────────────────

    _DOCKER_NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

    def _compose_file_for(request: Request) -> Path:
        repo_dir = getattr(request.app.state, "repo_dir", None)
        if repo_dir is None:
            raise HTTPException(500, "Repository path not configured")
        return repo_dir / "docker" / "docker-compose.yml"

    @router.post("/ui/docker/stack/restart")
    async def docker_stack_restart(request: Request):
        """Restart the entire docker-compose stack."""
        compose_file = _compose_file_for(request)
        if not compose_file.exists():
            raise HTTPException(404, "docker-compose.yml not found")
        data_dir = getattr(request.app.state, "data_dir", None)
        repo_dir = getattr(request.app.state, "repo_dir", None)
        env_file = (data_dir or repo_dir) / ".env" if (data_dir or repo_dir) else None

        cmd = ["docker", "compose", "-f", str(compose_file)]
        if env_file and env_file.exists():
            cmd.extend(["--env-file", str(env_file)])
        cmd.append("restart")

        async def _run():
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(proc.communicate(), timeout=120)
            except Exception:
                log.warning("docker compose restart failed", exc_info=True)

        task = asyncio.create_task(_run())
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        return {"status": "restarting"}

    @router.post("/ui/docker/container/{name}/restart")
    async def docker_container_restart(name: str, request: Request):
        """Restart a single container by container name."""
        if not _DOCKER_NAME_RE.match(name):
            raise HTTPException(400, "invalid container name")
        if not shutil.which("docker"):
            raise HTTPException(404, "docker CLI not found")

        async def _run():
            try:
                proc = await asyncio.create_subprocess_exec(
                    "docker", "restart", name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(proc.communicate(), timeout=60)
            except Exception:
                log.warning("docker restart %s failed", name, exc_info=True)

        task = asyncio.create_task(_run())
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        return {"status": "restarting", "container": name}

    # ── Observability stack toggle (Grafana + Prometheus + Loki + Alloy) ────
    # The four observability containers live behind a docker-compose
    # `observability` profile so the lean default install doesn't run them.
    # These endpoints flip the setup-config flag AND bring the four services
    # up/down to match.

    _OBSERVABILITY_SERVICES = ("grafana", "prometheus", "loki", "alloy")
    _OBSERVABILITY_MEM_NOTE = (
        "~500 MB additional RAM (grafana ~150, prometheus ~200, loki ~100, "
        "alloy ~50) plus ~50 GB of disk over a few months of retention."
    )

    def _setup_config_path(request: Request) -> Path:
        data_dir = getattr(request.app.state, "data_dir", None)
        if data_dir is None:
            raise HTTPException(500, "Gateway data_dir not configured")
        return data_dir / "setup-config.yaml"

    def _read_setup_config(request: Request) -> dict:
        path = _setup_config_path(request)
        if not path.exists():
            return {}
        try:
            import yaml as pyyaml
            return pyyaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            log.warning("Failed to parse setup-config.yaml", exc_info=True)
            return {}

    def _write_setup_config_flag(request: Request, key: str, value: bool) -> None:
        """Update a single boolean flag in setup-config.yaml in place."""
        import yaml as pyyaml
        path = _setup_config_path(request)
        data = _read_setup_config(request)
        data[key] = value
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            pyyaml.dump(data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
        try:
            import os as _os
            _os.chmod(path, 0o600)
        except OSError:
            pass

    async def _observability_container_states() -> dict[str, str]:
        """Return {service: state} for each of the four obs containers.

        State is one of: running, exited, absent. Uses `docker ps` rather
        than `docker compose ps` so it works whether or not the profile
        is currently active.
        """
        result: dict[str, str] = {s: "absent" for s in _OBSERVABILITY_SERVICES}
        if not shutil.which("docker"):
            return result
        try:
            rc, out, _ = await _run_cmd(
                ["docker", "ps", "-a", "--format", "{{.Names}}\t{{.State}}"],
                timeout=10,
            )
        except (asyncio.TimeoutError, FileNotFoundError):
            return result
        if rc != 0:
            return result
        for line in out.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t", 1)
            if len(parts) != 2:
                continue
            name, state = parts[0].strip(), parts[1].strip().lower()
            if name in result:
                result[name] = state
        return result

    @router.get("/ui/observability/status")
    async def observability_status(request: Request):
        """Report the enable flag, per-container state, and memory note."""
        cfg = _read_setup_config(request)
        states = await _observability_container_states()
        running = [s for s, st in states.items() if st == "running"]
        all_running = len(running) == len(_OBSERVABILITY_SERVICES)
        any_running = bool(running)
        return {
            "enabled": bool(cfg.get("install_observability", False)),
            "services": _OBSERVABILITY_SERVICES,
            "container_states": states,
            "all_running": all_running,
            "any_running": any_running,
            "memory_note": _OBSERVABILITY_MEM_NOTE,
            "grafana_url": "http://localhost:3000",
        }

    def _obs_compose_cmd(request: Request, *args: str) -> list[str]:
        """Build `docker compose -f ... --profile observability ...` for the
        stack — needed so the four profiled services are visible."""
        compose_file = _compose_file_for(request)
        data_dir = getattr(request.app.state, "data_dir", None)
        repo_dir = getattr(request.app.state, "repo_dir", None)
        env_file = (data_dir or repo_dir) / ".env" if (data_dir or repo_dir) else None
        cmd = ["docker", "compose", "-f", str(compose_file), "--profile", "observability"]
        if env_file and env_file.exists():
            cmd.extend(["--env-file", str(env_file)])
        cmd.extend(args)
        return cmd

    @router.post("/ui/observability/enable")
    async def observability_enable(request: Request):
        """Enable the obs stack: flip flag + `compose up -d` the four services."""
        if not shutil.which("docker"):
            raise HTTPException(404, "docker CLI not found")
        compose_file = _compose_file_for(request)
        if not compose_file.exists():
            raise HTTPException(404, "docker-compose.yml not found")

        _write_setup_config_flag(request, "install_observability", True)

        cmd = _obs_compose_cmd(request, "up", "-d", *_OBSERVABILITY_SERVICES)
        try:
            rc, out, err = await _run_cmd(cmd, timeout=180)
        except asyncio.TimeoutError:
            return JSONResponse(
                status_code=504,
                content={"error": "docker compose up timed out"},
            )
        if rc != 0:
            return JSONResponse(
                status_code=500,
                content={
                    "error": "docker compose up failed",
                    "stderr": (err or out)[-2000:],
                },
            )
        return {"status": "enabled", "output": (out or err)[-2000:]}

    @router.post("/ui/observability/disable")
    async def observability_disable(request: Request):
        """Disable the obs stack: stop+remove the four services, flip flag."""
        if not shutil.which("docker"):
            raise HTTPException(404, "docker CLI not found")

        # `rm -sf` stops and removes — survives if some are already stopped.
        # We explicitly enumerate the four services so we never accidentally
        # take down litellm/postgres (which would happen with a bare
        # `compose down`).
        cmd = _obs_compose_cmd(request, "rm", "-sf", *_OBSERVABILITY_SERVICES)
        try:
            rc, out, err = await _run_cmd(cmd, timeout=120)
        except asyncio.TimeoutError:
            return JSONResponse(
                status_code=504,
                content={"error": "docker compose rm timed out"},
            )

        # Flip the flag whether or not `rm` reported success — if there
        # were no containers to remove, the flag still needs to reflect
        # the user's intent.
        _write_setup_config_flag(request, "install_observability", False)

        if rc != 0:
            return JSONResponse(
                status_code=500,
                content={
                    "status": "disabled_with_errors",
                    "error": "docker compose rm reported errors",
                    "stderr": (err or out)[-2000:],
                },
            )
        return {"status": "disabled", "output": (out or err)[-2000:]}

    # TTS used to be a docker compose service (kokoro container); it now runs
    # as a gateway-managed mlx_audio.server process and is reached via the
    # generic /ui/services/{name}/{start,stop,enable,disable} endpoints.

    # ── Docker Model Runner + llmfit ──────────────────────────────────────────

    _DMR_MODEL_NAME_RE = re.compile(r"^[A-Za-z0-9._:/@-]{1,256}$")
    _DMR_PULL_TIMEOUT_SEC = 1800   # 30 min — large models can take a while
    _LLMFIT_TIMEOUT_SEC = 60

    async def _run_cmd(cmd: list[str], timeout: float) -> tuple[int, str, str]:
        """Run a subprocess, return (rc, stdout, stderr). No shell."""
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise
        return (
            proc.returncode or 0,
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
        )

    @router.get("/ui/dmr/llmfit/status")
    async def llmfit_status():
        """Report whether llmfit is installed and its version."""
        binary = shutil.which("llmfit")
        if not binary:
            return {
                "installed": False,
                "version": None,
                "install_hint": "brew install llmfit",
                "homepage": "https://github.com/AlexsJones/llmfit",
            }
        try:
            rc, out, _ = await _run_cmd([binary, "--version"], timeout=5)
            version = out.strip() if rc == 0 else None
        except Exception:
            version = None
        return {
            "installed": True,
            "version": version,
            "install_hint": None,
            "homepage": "https://github.com/AlexsJones/llmfit",
        }

    @router.get("/ui/dmr/llmfit/recommend")
    async def llmfit_recommend(request: Request):
        """
        Run `llmfit recommend` and filter to entries that have a GGUF source
        (DMR pulls GGUF via Docker Model Runner / llama.cpp). On Apple Silicon
        llmfit ranks by MLX runtime; rather than force llamacpp (which drops
        Metal accounting and yields no results in 0.9.x), we keep the default
        ranking and trim to GGUF-available entries client-side here.
        """
        binary = shutil.which("llmfit")
        if not binary:
            return JSONResponse(
                status_code=404,
                content={"error": "llmfit not installed", "install_hint": "brew install llmfit"},
            )

        params = request.query_params
        try:
            limit = max(1, min(int(params.get("limit", "8")), 25))
        except ValueError:
            limit = 8
        use_case = params.get("use_case", "").strip().lower()
        min_fit = params.get("min_fit", "good").strip().lower()

        # Apple Silicon: launchd-spawned processes can't always reach
        # system_profiler for GPU detection (TCC sandbox). Pass --memory so
        # at least VRAM size is correct; psutil gives us total system RAM,
        # and on unified-memory Macs llmfit treats --memory as both VRAM
        # and the effective memory budget.
        global_flags: list[str] = []
        try:
            import psutil
            total_gb = int(psutil.virtual_memory().total / (1024**3))
            if total_gb > 0:
                global_flags = ["--memory", f"{total_gb}G"]
        except Exception:
            pass

        # Over-request so the GGUF filter has room to keep `limit` results.
        cmd = [
            binary, *global_flags, "recommend",
            "--json",
            "--min-fit", min_fit if min_fit in {"perfect", "good", "marginal"} else "good",
            "-n", str(min(limit * 4, 50)),
        ]
        if use_case in {"general", "coding", "reasoning", "chat", "multimodal", "embedding"}:
            cmd += ["--use-case", use_case]

        try:
            rc, out, err = await _run_cmd(cmd, timeout=_LLMFIT_TIMEOUT_SEC)
        except asyncio.TimeoutError:
            return JSONResponse(status_code=504, content={"error": "llmfit timed out"})

        if rc != 0:
            return JSONResponse(
                status_code=500,
                content={"error": "llmfit failed", "stderr": err[:2000]},
            )
        try:
            data = json.loads(out)
        except json.JSONDecodeError as e:
            return JSONResponse(
                status_code=500,
                content={"error": f"llmfit returned non-JSON: {e}", "raw": out[:2000]},
            )

        official_only = params.get("official_only", "").strip().lower() in {"1", "true", "yes"}

        def _upstream_org(model_name: str) -> str:
            return (model_name or "").split("/", 1)[0].lower()

        def _annotate(m: dict) -> dict:
            """Tag each gguf_source with whether it's from the model's upstream org."""
            org = _upstream_org(m.get("name", ""))
            sources = list(m.get("gguf_sources") or [])
            for s in sources:
                repo = s.get("repo", "")
                source_org = repo.split("/", 1)[0].lower()
                s["is_official"] = bool(org) and source_org == org
            # Reorder so official source (if any) is first → frontend uses index 0.
            sources.sort(key=lambda s: not s.get("is_official"))
            m["gguf_sources"] = sources
            m["has_official_gguf"] = any(s.get("is_official") for s in sources)
            return m

        all_models = [_annotate(m) for m in data.get("models", [])]
        gguf_models = [m for m in all_models if m.get("gguf_sources")]
        if official_only:
            gguf_models = [m for m in gguf_models if m.get("has_official_gguf")]

        data["models"] = gguf_models[:limit]
        data["filtered_out"] = len(all_models) - len(gguf_models)
        data["official_only"] = official_only
        return data

    def _normalize_dmr_id(name: str) -> str:
        """Normalize a DMR tag/name for matching across `list` and `ps`.

        Strips `docker.io/ai/` and `docker.io/` prefixes but PRESERVES the
        tag (e.g. `:latest`). Comparisons happen by splitting on the colon
        in the caller.
        """
        name = (name or "").strip().lower()
        for prefix in ("docker.io/ai/", "docker.io/"):
            if name.startswith(prefix):
                return name[len(prefix):]
        return name

    async def _dmr_running() -> list[dict]:
        """Parse `docker model ps` output into [{name, backend, mode, until}].

        `docker model ps` has no JSON mode in current CLI versions, so we
        split each row on runs of 2+ spaces.
        """
        try:
            rc, out, _ = await _run_cmd(["docker", "model", "ps"], timeout=5)
        except (asyncio.TimeoutError, FileNotFoundError):
            return []
        if rc != 0 or not out.strip():
            return []
        lines = out.splitlines()
        if len(lines) <= 1:
            return []
        running: list[dict] = []
        for line in lines[1:]:
            if not line.strip():
                continue
            parts = re.split(r"\s{2,}", line.strip())
            if len(parts) < 1:
                continue
            running.append({
                "name": parts[0],
                "backend": parts[1] if len(parts) > 1 else "",
                "mode": parts[2] if len(parts) > 2 else "",
                "until": parts[3] if len(parts) > 3 else "",
            })
        return running

    def _llama_server_active_sha256() -> set[str]:
        """
        Return the set of DMR model IDs (sha256:<64-hex>) currently being
        served by a local llama-server process.

        DMR is just a downloader for this gateway — actual serving is via
        native llama-server, which is launched with `--model <bundle path>`
        where the bundle path contains the model's sha256. By extracting
        that sha and matching against `docker model list` IDs, we can flag
        which pulled models are "online".
        """
        try:
            import psutil
        except ImportError:
            return set()

        sha_re = re.compile(r"sha256[/\\]([a-f0-9]{64})")
        found: set[str] = set()
        for p in psutil.process_iter(["name", "cmdline"]):
            try:
                info = p.info
                name = (info.get("name") or "").lower()
                cmdline = info.get("cmdline") or []
                cl = " ".join(cmdline).lower() if cmdline else ""
                if "llama-server" not in name and "llama-server" not in cl:
                    continue
                m = sha_re.search(cl)
                if m:
                    found.add("sha256:" + m.group(1))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return found

    def _llama_server_active_model_paths() -> set[str]:
        """
        Return the set of `--model` paths currently being served by a local
        llama-server process. Both the raw path argument and its resolved
        canonical form are returned so we can match either side of a
        symlink (e.g. `/opt/storage/gguf/x.gguf` ↔ the real file on the
        external volume).
        """
        try:
            import psutil
        except ImportError:
            return set()

        found: set[str] = set()
        for p in psutil.process_iter(["name", "cmdline"]):
            try:
                info = p.info
                name = (info.get("name") or "").lower()
                cmdline = info.get("cmdline") or []
                cl = " ".join(cmdline).lower() if cmdline else ""
                if "llama-server" not in name and "llama-server" not in cl:
                    continue
                for i, arg in enumerate(cmdline):
                    if arg == "--model" and i + 1 < len(cmdline):
                        raw = cmdline[i + 1]
                        found.add(raw.lower())
                        try:
                            found.add(str(Path(raw).resolve()).lower())
                        except OSError:
                            pass
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return found

    def _local_gguf_search_paths(request: Request) -> list[Path]:
        """Directories to scan for side-loaded GGUF files.

        Sourced from (a) the parent directory of every services.*.args.--model
        currently configured, plus (b) `/opt/storage/gguf` if it exists.
        These are GGUFs the user dropped on disk directly (e.g. via curl)
        and that DMR therefore doesn't know about.
        """
        paths: dict[str, Path] = {}
        cm = getattr(request.app.state, "config_manager", None)
        if cm is not None:
            try:
                cfg = cm.config
            except Exception:
                cfg = {}
            for svc in (cfg.get("services") or {}).values():
                if not isinstance(svc, dict):
                    continue
                args = svc.get("args") if isinstance(svc.get("args"), dict) else {}
                mp = (args or {}).get("--model")
                if mp:
                    p = Path(mp).parent
                    if p.is_dir():
                        paths[str(p.resolve())] = p
        std = Path("/opt/storage/gguf")
        if std.is_dir():
            paths.setdefault(str(std.resolve()), std)
        return list(paths.values())

    def _scan_local_ggufs(request: Request) -> list[dict]:
        """Return DMR-shaped entries for .gguf files on disk outside DMR.

        Each entry carries `source: "file"` so the frontend can render it
        differently and skip the DMR-only `Delete` action.
        """
        served = _llama_server_active_model_paths()
        out: list[dict] = []
        seen_real: set[str] = set()
        for d in _local_gguf_search_paths(request):
            try:
                files = sorted(d.glob("*.gguf"))
            except OSError:
                continue
            for f in files:
                try:
                    real = str(f.resolve()).lower()
                except OSError:
                    real = str(f).lower()
                if real in seen_real:
                    continue
                seen_real.add(real)
                try:
                    st = f.stat()
                except OSError:
                    continue
                running = real in served or str(f).lower() in served
                out.append({
                    "id": "file:" + str(f),
                    "tags": [f.name],
                    "source": "file",
                    "path": str(f),
                    "running": running,
                    "created": int(st.st_mtime),
                    "config": {
                        "size": st.st_size,
                    },
                })
        return out

    @router.get("/ui/dmr/ps")
    async def dmr_ps():
        """List currently-running models in Docker Model Runner."""
        if not shutil.which("docker"):
            return {"running": []}
        return {"running": await _dmr_running()}

    @router.get("/ui/dmr/models")
    async def dmr_models(request: Request):
        """List models pulled to Docker Model Runner plus side-loaded local
        GGUFs, annotated with running state.

        DMR entries get `source: "dmr"` (default; absent for back-compat),
        side-loaded files get `source: "file"`. The frontend renders both
        and gates destructive actions on source.
        """
        local_files = _scan_local_ggufs(request)

        if not shutil.which("docker"):
            return {"models": local_files, "running": []}

        try:
            rc, out, err = await _run_cmd(
                ["docker", "model", "list", "--json"], timeout=10,
            )
        except asyncio.TimeoutError:
            return JSONResponse(status_code=504, content={"error": "docker timed out"})
        if rc != 0:
            # Docker present but `model list` failed (DMR not enabled, daemon
            # down, etc). Don't lose the side-loaded files in that case.
            return {
                "models": local_files,
                "running": [],
                "warning": "docker model list failed: " + (err[:300] or "no stderr"),
            }
        try:
            models = json.loads(out) if out.strip() else []
        except json.JSONDecodeError:
            models = []

        running = await _dmr_running()

        # Two paths for "running" state:
        # 1. Models served by a local llama-server (the common case here) —
        #    matched by the sha256 in the --model bundle path against the
        #    DMR model ID. This is exact and unambiguous.
        # 2. Models loaded into DMR's own runtime via `docker model run`
        #    (rare for this gateway). Reported by `docker model ps` and
        #    matched by tag base/disambiguation as before.
        served_shas = _llama_server_active_sha256()
        for m in models:
            m["running"] = m.get("id") in served_shas

        base_to_pairs: dict[str, list[tuple[int, str, str]]] = {}
        for idx, m in enumerate(models):
            for t in m.get("tags") or []:
                norm = _normalize_dmr_id(t)
                base, _, tag = norm.partition(":")
                base_to_pairs.setdefault(base, []).append((idx, norm, tag))

        for r in running:
            rn = _normalize_dmr_id(r["name"])
            r_base, _, r_tag = rn.partition(":")
            candidates = base_to_pairs.get(r_base, [])
            if not candidates:
                continue
            if r_tag:
                for idx, norm, _t in candidates:
                    if norm == rn:
                        models[idx]["running"] = True
                        break
            else:
                latest = next((c for c in candidates if c[2] == "latest"), None)
                if latest is not None:
                    models[latest[0]]["running"] = True
                elif len(candidates) == 1:
                    models[candidates[0][0]]["running"] = True

        return {"models": models + local_files, "running": running}

    @router.post("/ui/dmr/rm")
    async def dmr_rm(request: Request):
        """Remove a downloaded model from Docker Model Runner."""
        body = await request.json()
        model = (body.get("model") or "").strip()
        if not model:
            return JSONResponse(status_code=400, content={"error": "model is required"})
        if not _DMR_MODEL_NAME_RE.match(model):
            return JSONResponse(status_code=400, content={"error": "invalid model name"})
        if not shutil.which("docker"):
            return JSONResponse(status_code=404, content={"error": "docker CLI not found"})
        try:
            rc, out, err = await _run_cmd(
                ["docker", "model", "rm", "-f", model], timeout=30,
            )
        except asyncio.TimeoutError:
            return JSONResponse(status_code=504, content={"error": "docker rm timed out"})
        if rc != 0:
            return JSONResponse(
                status_code=500,
                content={"error": "docker model rm failed", "stderr": err[:2000] or out[:2000]},
            )
        return {"status": "removed", "model": model}

    @router.post("/ui/dmr/pull")
    async def dmr_pull(request: Request):
        """Pull a model via Docker Model Runner."""
        body = await request.json()
        model = (body.get("model") or "").strip()
        if not model:
            return JSONResponse(status_code=400, content={"error": "model is required"})
        if not _DMR_MODEL_NAME_RE.match(model):
            return JSONResponse(status_code=400, content={"error": "invalid model name"})
        if not shutil.which("docker"):
            return JSONResponse(status_code=404, content={"error": "docker CLI not found"})

        try:
            rc, out, err = await _run_cmd(
                ["docker", "model", "pull", model], timeout=_DMR_PULL_TIMEOUT_SEC,
            )
        except asyncio.TimeoutError:
            return JSONResponse(
                status_code=504,
                content={"error": f"pull timed out after {_DMR_PULL_TIMEOUT_SEC}s"},
            )
        combined = (out + ("\n" + err if err else ""))[-4000:]
        return {
            "status": "success" if rc == 0 else "failed",
            "model": model,
            "output": combined,
        }

    @router.get("/ui/dmr/pull/stream")
    async def dmr_pull_stream(request: Request):
        """
        Stream `docker model pull <model>` as server-sent events.

        Each progress line on stdout/stderr becomes one `progress` event;
        a final `done` event carries the exit status. Clients consume with
        EventSource() in the browser.
        """
        model = (request.query_params.get("model") or "").strip()
        if not model:
            return JSONResponse(status_code=400, content={"error": "model is required"})
        if not _DMR_MODEL_NAME_RE.match(model):
            return JSONResponse(status_code=400, content={"error": "invalid model name"})
        if not shutil.which("docker"):
            return JSONResponse(status_code=404, content={"error": "docker CLI not found"})

        def _sse(event: str, data: str) -> bytes:
            # SSE: data lines may not contain raw newlines; split if any sneak through.
            lines = data.splitlines() or [""]
            payload = "".join(f"data: {line}\n" for line in lines)
            return f"event: {event}\n{payload}\n".encode("utf-8")

        async def _gen():
            yield _sse("start", f"Pulling {model}...")
            try:
                proc = await asyncio.create_subprocess_exec(
                    "docker", "model", "pull", model,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
            except Exception as e:
                yield _sse("done", json.dumps({"status": "failed", "error": str(e)}))
                return

            assert proc.stdout is not None
            try:
                async for raw in proc.stdout:
                    line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                    if line:
                        yield _sse("progress", line)
            except asyncio.CancelledError:
                # Client disconnected. Don't kill the subprocess — Docker's daemon
                # is doing the real work and abandoning the CLI mid-pull leaves
                # things in a weird state. Just stop streaming.
                raise

            rc = await proc.wait()
            yield _sse("done", json.dumps({
                "status": "success" if rc == 0 else "failed",
                "model": model,
                "returncode": rc,
            }))

        return StreamingResponse(
            _gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",  # disable proxy buffering if any
            },
        )

    return router
