# LLM Gateway

A single place to send all your LLM traffic on an Apple Silicon Mac. **LiteLLM Proxy** does the routing, auth, and spend tracking; a small **management app** gives you a local dashboard, config editor, and control over local services (Ollama, llama.cpp, Whisper). Point Claude Code, Cursor, or any OpenAI-compatible client at one endpoint and route to OpenRouter (e.g. Claude) or local models.

---

## Architecture (simple view)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  YOUR MACHINE (Mac Mini or Mac)                                              │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Management app (Python) — port 8080                                  │    │
│  │  • Web dashboard: config, service status, Ollama model pull           │    │
│  │  • Starts/stops/monitors: Ollama, llama-server, whisper-server        │    │
│  │  • Optional: run provisioning (Docker, Node, Claude Code, etc.)       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                        │                                      │
│  ┌────────────────────────────────────┼────────────────────────────────────┐ │
│  │  Docker stack                       │                                    │ │
│  │  • LiteLLM Proxy (port 4000) ◀──────┼─── THE API your clients call       │ │
│  │  • PostgreSQL (keys, spend)         │                                    │ │
│  │  • Grafana, Prometheus, Loki        │                                    │ │
│  └────────────────────────────────────┴────────────────────────────────────┘ │
│                                        │                                      │
│  Local inference (optional):           │                                      │
│  • Ollama (port 11434) — managed by dashboard, Metal GPU                      │
│  • llama-server / whisper-server — configurable in config                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
          ┌─────────────────────────────┼─────────────────────────────┐
          │                             │                             │
          ▼                             ▼                             ▼
   Claude Code                   Cursor IDE              Any OpenAI SDK / curl
          │                             │                             │
          └─────────────────────────────┼─────────────────────────────┘
                                        │
                                        ▼
   LiteLLM Proxy routes to:  OpenRouter (Claude, GPT, etc.)  or  Ollama (local)
```

- **Clients** (Claude Code, Cursor, scripts) talk only to **LiteLLM Proxy** at `http://<this-mac>:4000`.
- **You** use the **management dashboard** at `http://localhost:8080` to edit config, see service status, and pull Ollama models. The dashboard can start the Docker stack and manage local inference services.

---

## What’s in this repo

| Piece | Purpose |
|-------|--------|
| **LiteLLM Proxy** (Docker) | One API endpoint; routes requests to OpenRouter or Ollama; virtual keys, spend tracking, dashboard at `/ui`. |
| **Management app** (Python) | Web UI + REST API; config editor; starts/monitors Ollama (and optional llama.cpp / Whisper). |
| **Provisioning** (`scripts/setup-llmgateway.py`) | Installs and checks: Git, Node, Claude Code CLI, Docker Desktop, Ollama, SSH, `.env`, and starts the Docker stack. |
| **Bootstrap** (`bootstrap.sh`) | Ensures Python 3.11+ and deps, then runs the management app (or `--status` / `--install` for launchd). |

No custom proxy code: routing, auth, and usage are handled by LiteLLM. This repo is config, Docker stack, and the management tooling.

---

## What you need

- Mac with Apple Silicon (M1/M2/M3/M4)
- [OpenRouter API key](https://openrouter.ai/keys) (covers Anthropic, OpenAI, and many others)
- Docker Desktop (provisioning can install it)

---

## Get running

### 1. Clone and bootstrap

```bash
git clone https://github.com/<owner>/LLMGateway.git ~/src/LLMGateway
cd ~/src/LLMGateway
./bootstrap.sh
```

This installs Python 3.11+, pip, and dependencies, then **starts the management app** (dashboard at http://localhost:8080). Leave it running in that terminal, or use `--install` to run it as a launchd agent (see below).

### 2. Provision the rest (first time)

In another terminal, from the repo root:

```bash
cd ~/src/LLMGateway
python3 scripts/setup-llmgateway.py
```

This installs/checks: Xcode CLT, Homebrew, Node, Claude Code CLI, Docker Desktop, Ollama, SSH, creates `.env` from `.env.example`, and brings up the Docker stack (LiteLLM, PostgreSQL, Grafana, Prometheus, Loki). Safe to run again.

To only check status (no changes):

```bash
python3 scripts/setup-llmgateway.py --status
```

### 3. Add your API keys

```bash
cp .env.example .env
# Edit .env: set OPENROUTER_API_KEY and LITELLM_MASTER_KEY
```

### 4. Start local models (optional)

If you use local models (e.g. `heartbeat` → Ollama):

```bash
ollama serve
ollama pull llama3.2:3b
```

The management dashboard can also start and monitor Ollama if it’s enabled in `config/llmgateway.yaml`.

### 5. Verify

- **LiteLLM Proxy:** http://localhost:4000/health/liveliness → `{"status":"healthy"}`
- **LiteLLM UI:** http://localhost:4000/ui (login with `LITELLM_MASTER_KEY`)
- **Management dashboard:** http://localhost:8080

---

## Management app commands

Run from the repo with Python (or after `./bootstrap.sh` you can pass these through bootstrap):

| Command | Effect |
|---------|--------|
| `./bootstrap.sh` | Start the gateway (dashboard + service manager). Default. |
| `./bootstrap.sh --status` | Print status (platform, memory, services, launchd). No server. |
| `./bootstrap.sh --install` | Install launchd agent so the gateway starts on login. |
| `./bootstrap.sh --uninstall` | Remove the launchd agent. |

Provisioning (install Docker, Ollama, etc.) is separate: `python3 scripts/setup-llmgateway.py`.

---

## Using the dashboard

Open **http://localhost:8080**.

- **Config** — Edit gateway settings (ports, which services are enabled, health check intervals). Stored in `config/llmgateway.yaml` (overrides `config/llmgateway.defaults.yaml`).
- **Services** — See status of Ollama, llama-server, Whisper; start/stop/restart.
- **Ollama** — Pull models from the UI.
- **REST API** — Read-only: `GET /api/status`, `GET /api/services`, `GET /api/config`, `GET /api/health`.

LiteLLM’s own UI (keys, spend, models) is at **http://localhost:4000/ui** (use `LITELLM_MASTER_KEY`).

---

## Connect Claude Code or Cursor

Use the **LiteLLM Proxy** endpoint and a key (master or a generated virtual key).

**Claude Code:**

```bash
export ANTHROPIC_BASE_URL=http://<this-mac-ip-or-hostname>:4000
export ANTHROPIC_API_KEY=sk-gateway-master-change-me
```

**Cursor:** In settings set API Base URL to `http://<this-mac>:4000/v1` and API Key to your master or virtual key.

To create a dedicated key (recommended):

```bash
curl -X POST http://localhost:4000/key/generate \
  -H "Authorization: Bearer sk-gateway-master-change-me" \
  -H "Content-Type: application/json" \
  -d '{"key_alias": "claude-code", "max_budget": 50.0, "budget_duration": "monthly"}'
```

Use the returned key as `ANTHROPIC_API_KEY` or in Cursor.

---

## How routing works

Clients send requests to LiteLLM with a **model name**. LiteLLM maps that to real backends using `litellm-config.yaml`.

| You request | Routed to (default) |
|-------------|----------------------|
| `deep-reasoning` | Claude Sonnet 4 (OpenRouter or direct Anthropic) |
| `coding` | Claude Sonnet 4 (OpenRouter or direct Anthropic) |
| `vision` | Claude Sonnet 4 (OpenRouter) |
| `heartbeat` | Ollama (e.g. llama3.2:1b) — local |
| `local-only` | Ollama (e.g. llama3.2:3b) — local |
| Others | See `litellm-config.yaml` (e.g. `cheap-research`, `budget`, aliases) |

Editing `litellm-config.yaml` (and restarting the LiteLLM container or stack) changes routing. You can also add models at runtime via the LiteLLM UI or API.

---

## Configuration at a glance

| What | Where |
|------|--------|
| Gateway (dashboard port, services, health, Docker) | `config/llmgateway.defaults.yaml` (defaults) and `config/llmgateway.yaml` (your overrides). Edit in dashboard or on disk. |
| LiteLLM (models, routing, fallbacks) | `litellm-config.yaml` at repo root. |
| API keys | `.env` (from `.env.example`). |

---

## Project structure

```
LLMGateway/
├── bootstrap.sh                 # Install Python/deps, run management app (or --status / --install)
├── requirements.txt             # Python deps for management app
├── .env.example                 # Template for API keys
├── litellm-config.yaml          # LiteLLM Proxy: routing, models, providers
├── config/
│   └── llmgateway.defaults.yaml # Gateway defaults (do not edit; override in llmgateway.yaml)
├── scripts/
│   ├── llmgateway.py            # Management app: web UI, service manager, launchd
│   ├── setup-llmgateway.py      # Provisioning: Git, Node, Docker, Ollama, .env, Docker stack
│   ├── config/                  # Config load/save/validate
│   ├── launchd/                 # macOS launchd install/uninstall
│   ├── services/                # Ollama, llama.cpp, Whisper service managers
│   ├── steps/                   # Provisioning steps (Docker, Ollama, etc.)
│   └── web/                     # Dashboard HTML, API, UI routes
└── docker/
    ├── docker-compose.yml       # LiteLLM, PostgreSQL, Grafana, Prometheus, Loki, Alloy
    ├── prometheus/
    ├── alloy/
    └── grafana/
```

---

## Virtual keys and observability

**Virtual keys** — In LiteLLM UI (http://localhost:4000/ui) you can create keys with budgets, rate limits, and model restrictions. Use these instead of the master key for Claude Code, Cursor, or scripts.

**Observability** — Grafana at http://localhost:3000 (default login `admin` / `llmgateway`), Prometheus at http://localhost:9090. LiteLLM exposes `/metrics`; logs can be collected via Grafana Alloy (see `docker/alloy`).

---

## Optional: local llama.cpp or Whisper

In `config/llmgateway.yaml` (or the dashboard) you can enable `fast_model` / `deep_model` (llama-server) or `whisper`. Set `enabled: true` and fill in paths (e.g. `--model` for the GGUF file). The gateway will start and monitor them. LiteLLM can route to these via `litellm-config.yaml` (e.g. `openai/`-compatible endpoint on the port you set).

Ollama runs on the host (not in Docker) so it can use Apple Metal. The Docker stack reaches it via `host.docker.internal:11434`.
