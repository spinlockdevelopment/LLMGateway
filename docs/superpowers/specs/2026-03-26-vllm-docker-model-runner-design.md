# Design: Docker Model Runner + llmfit Integration

**Date:** 2026-03-26
**Branch:** docker-vLLM
**Status:** Approved

## Summary

Replace the gateway's local model infrastructure (Ollama, llama.cpp service managers, BaseService/ServiceRegistry framework) with Docker Model Runner (DMR) for all text LLM inference. Integrate llmfit for hardware-aware model recommendations. Keep whisper.cpp as a standalone process for audio transcription.

## Goals

- **Simplify** — Remove ~3 service managers and the process lifecycle framework. Docker Desktop manages model processes.
- **Unify local inference** — One backend (DMR) instead of three (Ollama, llama.cpp, manual processes).
- **Smart model selection** — llmfit recommends models matched to hardware at setup and via dashboard.
- **Keep whisper** — Audio transcription is a different modality DMR doesn't cover.

## Non-Goals

- Multi-platform support beyond macOS Apple Silicon (don't over-engineer).
- Native Anthropic API on local models (LiteLLM already translates).
- Embedding llmfit as a library (CLI tool, shelled out to).
- Auto-pulling models without user confirmation.

## Target Platform

- macOS Apple Silicon (primary)
- Docker Desktop 4.62+ with vllm-metal support
- DMR auto-selects engine: vllm-metal for safetensors, llama.cpp for GGUF

---

## Architecture

```
Clients (Claude Code, Cursor)
    |
    v
LiteLLM Proxy (port 4000, Docker)
    |
    +---> Remote providers (OpenRouter, Anthropic)
    |
    +---> Docker Model Runner (port 12434, managed by Docker Desktop)
    |       └── vLLM-metal / llama.cpp engines (auto-selected by format)
    |
    └──-> Whisper.cpp (standalone process, managed by gateway)

Gateway Management Service (port 8080)
    +-- DMR status + model management (via DMR REST API + docker CLI)
    +-- llmfit integration (CLI tool, hardware-aware model recommendations)
    +-- Whisper process management (lightweight, standalone)
    └── Dashboard UI (updated panels)
```

### What's Removed

- `BaseService` / `ServiceRegistry` / `ServiceState` enum — replaced by direct DMR API calls + simple whisper manager
- `scripts/services/ollama.py` — deleted
- `scripts/services/llamacpp.py` — deleted
- `scripts/services/__init__.py` — current contents removed (registry framework)
- Ollama binary dependency
- llama-server binary dependency
- Health-check/auto-restart/exponential-backoff machinery for LLM services

### What's Unchanged

- LiteLLM Proxy + PostgreSQL + observability stack (Docker Compose)
- Config system (adapted for new shape)
- Dashboard framework (updated panels)
- Secrets management
- Remote provider routing

---

## Component: Docker Model Runner Integration

**File:** `scripts/services/docker_model_runner.py`

A plain Python class wrapping DMR's REST API and Docker CLI. Not a BaseService subclass.

### Responsibilities

| Operation | Method | Implementation |
|---|---|---|
| Status check | `is_available()` | `GET http://localhost:12434/engines/v1/models` |
| List models | `list_models()` | Same endpoint, parse response |
| Pull model | `pull_model(name)` | Shell out to `docker model pull <name>` |
| Remove model | `remove_model(name)` | Shell out to `docker model rm <name>` |
| Inspect model | `inspect_model(name)` | Shell out to `docker model inspect <name>` |
| Engine info | Derived from model format | GGUF → llama.cpp, safetensors → vllm-metal |

### What It Does NOT Do

- Process management — Docker Desktop owns the model runner process
- Health checks / auto-restart — Docker handles this
- Memory tracking — DMR loads/unloads models on-demand automatically

### Gateway REST API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/dmr/status` | GET | Is Docker Model Runner responding? |
| `/api/models` | GET | List pulled DMR models |
| `/ui/models/pull` | POST | Pull a model (body: `{"model": "ai/qwen2.5-coder:7b"}`) |
| `/ui/models/{name}` | DELETE | Remove a model |

---

## Component: llmfit Integration

**File:** `scripts/services/llmfit.py`

Wraps the `llmfit` CLI tool. Optional dependency — gateway functions without it.

### Setup-Time Usage (setup-llmgateway.py)

1. Check if `llmfit` binary is on PATH
2. If not, offer to install: `curl -fsSL https://llmfit.axjns.dev/install.sh | sh`
3. Run `llmfit recommend --json --limit 5` for top hardware-matched models
4. Present recommendations to user
5. User selects which to pull → `docker model pull` for each

### Dashboard Usage

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/llmfit/recommendations` | GET | Run `llmfit recommend --json`, optional query params: `use_case`, `limit` |
| `/api/llmfit/system` | GET | Run `llmfit system --json`, show detected hardware |

### Dashboard Panel: "Discover Models"

- Table of recommendations: model name, composite score, memory fit, quality, speed
- "Pull" button per row → calls `/ui/models/pull`
- Filter by use-case (coding, chat, reasoning)
- "Refresh" button to re-run recommendations

---

## Component: Whisper.cpp Manager

**File:** `scripts/services/whisper_manager.py`

Standalone process manager for whisper.cpp. Extracted from current `whisper.py` but without BaseService/ServiceRegistry inheritance.

### Capabilities

- Start/stop whisper-server process (SIGTERM → 10s → SIGKILL)
- Health check against configured HTTP endpoint
- Auto-restart on crash (simple retry with fixed delay, no exponential backoff)
- Three states: `running`, `stopped`, `failed`

### Config

Lives under `services.whisper` in `llmgateway.defaults.yaml` (same location, simplified).

---

## Configuration Changes

### New `config/llmgateway.defaults.yaml`

```yaml
gateway:
  host: "127.0.0.1"
  port: 8080
  log_level: "INFO"

docker_model_runner:
  enabled: true
  host: "localhost"
  port: 12434
  api_base: "http://localhost:12434/engines/v1"

services:
  whisper:
    enabled: false
    binary: "whisper-server"
    args:
      --model: ""
      --host: "127.0.0.1"
      --port: "8178"
    health_check_url: "http://localhost:8178/health"

llmfit:
  auto_recommend_on_setup: true
  default_limit: 5

docker:
  auto_launch: true
  compose_file: "docker/docker-compose.yml"
```

### Removed Config Sections

- `services.ollama` — no longer needed
- `services.fast_model` — no longer needed
- `services.deep_model` — no longer needed
- `health_check` (interval, backoff, max_restart_attempts) — DMR handles this
- `memory` (reserved_gb, pressure_threshold) — DMR manages model memory

### LiteLLM Config Updates (`litellm-config.yaml`)

Local model entries change from Ollama/llama.cpp endpoints to DMR:

```yaml
# Before:
- model_name: local-only
  litellm_params:
    model: ollama_chat/llama3.2:3b
    api_base: http://host.docker.internal:11434

# After:
- model_name: local-only
  litellm_params:
    model: openai/ai/qwen2.5-coder:7b
    api_base: http://host.docker.internal:12434/engines/v1
    api_key: not-needed
```

Pseudo-model routing (manual mapping) stays intentional. Dashboard shows available DMR models to help wire them up.

---

## Dashboard Changes

### Remove

- Ollama service panel (start/stop/status)
- llama.cpp service panel
- Ollama model pull UI
- Per-service memory budget display

### Add

- **Docker Model Runner** status card — green/red health indicator, engine info
- **Local Models** panel — pulled DMR models list (name, size, format, engine), pull/remove actions
- **Discover Models** panel — llmfit recommendations table with pull buttons, use-case filter
- **System Info** card — llmfit hardware detection (CPU, RAM, GPU type)

### Keep

- Whisper service panel (start/stop/status)
- Config editor
- Secrets management
- Remote provider status (via LiteLLM health)

---

## Setup Changes (`setup-llmgateway.py`)

### Remove Steps

- Ollama installation/verification
- llama-server binary check
- Ollama model pulling

### Add Steps

1. Verify Docker Desktop is installed and running
2. Enable DMR TCP access: `docker desktop enable model-runner --tcp 12434`
3. Verify DMR is responding at `localhost:12434`
4. Check for / offer to install `llmfit`
5. Run llmfit recommendations, present to user
6. Pull user-selected models via `docker model pull`

### Keep Steps

- Docker Compose stack setup (LiteLLM, Postgres, observability)
- Config file creation/merging
- Secrets/.env setup

---

## File Changes

### Delete

| File | Reason |
|---|---|
| `scripts/services/ollama.py` | Replaced by DMR |
| `scripts/services/llamacpp.py` | Replaced by DMR |
| `scripts/services/__init__.py` | BaseService/ServiceRegistry framework removed |

### Create

| File | Purpose |
|---|---|
| `scripts/services/docker_model_runner.py` | DMR REST API + CLI wrapper |
| `scripts/services/llmfit.py` | llmfit CLI wrapper |
| `scripts/services/whisper_manager.py` | Standalone whisper process manager |

### Modify

| File | Changes |
|---|---|
| `scripts/llmgateway.py` | Remove registry init, wire up DMR + whisper manager |
| `scripts/web/api.py` | New endpoints: `/api/dmr/status`, `/api/models`, `/api/llmfit/*` |
| `scripts/web/ui.py` | New UI actions for model pull/remove/discover; remove ollama/llamacpp actions |
| `scripts/web/dashboard.html` | New panels (DMR status, models, discover); remove old service panels |
| `scripts/setup-llmgateway.py` | DMR verification, llmfit install, model recommendations |
| `config/llmgateway.defaults.yaml` | New config shape (DMR, whisper-only services, llmfit) |
| `litellm-config.yaml` | Local model entries point to DMR on port 12434 |
| `scripts/config/schema.py` | Validation updated for new config shape |
| `scripts/config/manager.py` | Remove ollama/llamacpp-specific config logic if any |

---

## Request Flow: Local Model Inference

```
1. Client sends request to gateway (OpenAI or Anthropic format)
2. LiteLLM Proxy receives request, resolves pseudo-model to deployment
3. LiteLLM translates to OpenAI format if needed
4. Request forwarded to http://host.docker.internal:12434/engines/v1/chat/completions
5. DMR loads model into memory on-demand (if not already loaded)
6. DMR selects engine (vllm-metal or llama.cpp) based on model format
7. Inference runs, response returned
8. LiteLLM translates response back if client used Anthropic format
9. DMR unloads model when idle
```

## Request Flow: Model Discovery

```
1. User opens dashboard, navigates to "Discover Models"
2. Dashboard calls GET /api/llmfit/recommendations
3. Gateway shells out to: llmfit recommend --json --limit 10
4. llmfit detects hardware, scores models, returns JSON
5. Dashboard renders recommendation table
6. User clicks "Pull" on a model
7. Dashboard calls POST /ui/models/pull with model name
8. Gateway shells out to: docker model pull <model>
9. Model appears in "Local Models" panel
10. User can then map it to a pseudo-model route in config
```
