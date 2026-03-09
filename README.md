# LLM Gateway

A single place to send all your LLM traffic on an Apple Silicon Mac. **LiteLLM Proxy** does the routing, auth, and spend tracking; a small **management interface** gives you a local dashboard with config editor and control over local services (Ollama, llama.cpp, Whisper). Point Claude Code, Cursor, Agents or any compatible client at one endpoint to route to local models or your subscriptions (e.g. Claude, OpenAI, Gemini, OpenRouter).

---

## Architecture (simple view)

```
                    Tools / Agents
         Claude Code · Cursor · OpenClaw · (etc)
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  YOUR MACHINE                                                               │
│                                                                             │
│  ┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐ │
│  │  Management svc      │ │  LiteLLM Proxy       │ │  Observability       │ │
│  │  port 8080           │ │  port 4000           │ │  Grafana · port 3000 │ │
│  └──────────┬───────────┘ └──────────┬───────────┘ └──────────┬───────────┘ │
│             │                        │                        │             │
│             └────────────────────────┼────────────────────────┘             │
│                                                                             │
│                              Docker stack                                   │
│         LiteLLM · PostgreSQL · Grafana · Prometheus · Loki · Alloy          │
│                                       │                                     │
│                                       │               ┌──────────────────┐  │
│             LiteLLM Proxy ────────────┼────────────▶ │ Local inference  │  │
│                 │                     │               │ · Ollama         │  │
│                 │                     ▼               │ · llama-server   │  │
│                 │                                     │ · whisper-server │  │
│                 │                                     └──────────────────┘  │
└─────────────────┼───────────────────────────────────────────────────────────┘
                  │
                  ▼
                  Cloud Services
         Claude · OpenAI · OpenRouter · (etc)


```

- **Tools/agents** (e.g. Claude Code, Cursor, OpenClaw) send requests to **LiteLLM Proxy** at `http://<this-mac>:4000`.
- **Your machine** runs the **management app** (port 8080), **LiteLLM Proxy** (port 4000), and **observability** (Grafana), linked to the **Docker stack** (LiteLLM, PostgreSQL, Grafana, Prometheus, Loki, Alloy).
- **LiteLLM** routes traffic **out** to **cloud services** (OpenRouter, Anthropic, etc.) and **down** to **local inference** (Ollama, llama-server, Whisper).

---

## What’s in this repo

| Piece | Purpose |
|-------|--------|
| **LiteLLM Proxy** (Docker) | One API endpoint; routes requests to local models, Anthropic, OpenAI, OpenRouter, etc; virtual keys, spend tracking, dashboard at `/ui`. |
| **Management app** (Python) | Web UI + REST API; config editor; starts/monitors local models (Ollama / llama.cpp / Whisper). |
| **Bootstrap** (`bootstrap-llmgateway.sh`) | Ensures OS-level prerequisites (Xcode CLT, Homebrew, Git, Python 3.11+, Docker Desktop) are installed, creates a Python venv, then hands off to the setup script. Only requests `sudo` when a missing dependency requires it. Can clone the repo into `~/src/LLMGateway` when run via curl. |
| **Setup** (`scripts/setup-llmgateway.py`) | Application-level provisioning: Git repo, Node.js, Claude Code CLI, Docker stack, `.env`, optional components (Ollama, llama-server, whisper-server, SSH), and installs the management console as a launchd agent. Runs as a standard user — no admin required. |

This repo is config, Docker stack, and the management tooling for running LiteLLM which handles routing, auth, and usage. 

---

## What you need

- Mac with Apple Silicon (M1/M2/M3/M4)
- API keys for the providers you want to use: [OpenRouter](https://openrouter.ai/keys), [Anthropic](https://console.anthropic.com/), [OpenAI](https://platform.openai.com/settings/organization/api-keys), etc.
- Docker Desktop (bootstrap installs it automatically if missing)

---

## Get running

### 1. Bootstrap (OS-level prerequisites)

The bootstrap script checks for Homebrew, Git, Python 3.11+, and Docker Desktop. If everything is already installed, **no elevated privileges are needed**. If any dependency is missing, the script asks you before installing (use `--install` or `--launch` to skip the prompt). Installation requires `sudo` for the missing tools only (Xcode CLT, Homebrew, Docker Desktop, etc.), then the script drops back to your normal user account for the remaining steps. After prerequisites are in place, the bootstrap creates a Python virtual environment at `~/src/LLMGateway/.venv` and installs pip dependencies.

**Option A — clone then run (recommended):**

```bash
git clone https://github.com/spinlockdevelopment/LLMGateway.git ~/src/LLMGateway
cd ~/src/LLMGateway
./bootstrap-llmgateway.sh            # interactive (asks before each step)
./bootstrap-llmgateway.sh --install  # auto-install deps, ask before launching setup
./bootstrap-llmgateway.sh --launch   # fully automatic (no prompts)
```

**Option B — curl (script clones into `~/src/LLMGateway` for you):**

```bash
curl -fsSL https://raw.githubusercontent.com/spinlockdevelopment/LLMGateway/main/bootstrap-llmgateway.sh | bash
```

### 2. Setup (application provisioning)

The setup script is launched automatically at the end of bootstrap. It provisions application-level components: Git repo sync, Node.js, Claude Code CLI, Docker stack, `.env` from template, and optional components (Ollama, llama-server, whisper-server, SSH). It also installs the management console as a launchd agent.

> **The setup script should be run as a standard user account, not an administrator.** It does not require `sudo` or elevated privileges. If run as root, it will warn you and ask for confirmation before continuing. Running as root can cause file ownership issues with the venv and launchd agent.

To re-run setup manually (safe to run repeatedly — all steps are idempotent):

```bash
cd ~/src/LLMGateway
.venv/bin/python3 scripts/setup-llmgateway.py
```

To only check status (no changes):

```bash
.venv/bin/python3 scripts/setup-llmgateway.py --status
```

### 3. Add your API keys

Use the dashboard **Secrets** tab (http://localhost:8080) to edit `.env`, or copy and edit by hand:

```bash
cp .env.example .env
# Edit .env: set any API keys you need; LITELLM_MASTER_KEY is used for the proxy UI and virtual keys
```

`.env.example` is the template: it lists API keys and base URLs (with defaults) for OpenRouter, Anthropic, OpenAI, Google, xAI, Azure, Perplexity, and others, plus optional LiteLLM OAuth 2.0 variables. Everything is optional. Base URL vars are only written to `.env` when their associated API key is set. Blank entries are not written when saving from the UI.

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

## Commands

**Bootstrap:**

| Command | Effect |
|---------|--------|
| `./bootstrap-llmgateway.sh` | Interactive — asks before installing missing deps, asks before launching setup. |
| `./bootstrap-llmgateway.sh --install` | Auto-installs missing deps (no prompt), but still asks before launching setup. |
| `./bootstrap-llmgateway.sh --launch` | Fully automatic — installs deps and launches setup with no prompts. |

**Setup (run directly or launched by bootstrap):**

| Command | Effect |
|---------|--------|
| `.venv/bin/python3 scripts/setup-llmgateway.py` | Application provisioning: Docker stack, Node, Claude Code, optional components, management console. Safe to re-run. |
| `.venv/bin/python3 scripts/setup-llmgateway.py --status` | Status check only (no changes made). |
| `.venv/bin/python3 scripts/setup-llmgateway.py --verbose` | Setup with debug-level output. |

You can also pass `--status` or `--verbose` through bootstrap: `./bootstrap-llmgateway.sh --launch --status`.

---

## Using the dashboard

Open **http://localhost:8080**.

- **Config** — Edit gateway settings (ports, which services are enabled, health check intervals). Stored in `config/llmgateway.yaml` (overrides `config/llmgateway.defaults.yaml`).
- **Secrets** — Edit `.env`: API keys, provider base URLs (OpenRouter, OpenAI, Anthropic, etc.), optional OAuth 2.0 vars. Template is `.env.example`; blank entries are not saved. Saving automatically restarts the LiteLLM container if any relevant keys changed.
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

**Web search (search API)** — LiteLLM supports web search via the same proxy. Use `/chat/completions` with `web_search_options` on search-capable models (e.g. OpenAI `gpt-4o-search-preview`, xAI `grok-3`, Anthropic Claude, Gemini), or `/responses` with the `web_search_preview` tool on regular models. You can set default `web_search_options` in `litellm-config.yaml`. See [LiteLLM Web Search](https://docs.litellm.ai/docs/completion/web_search) for endpoints, providers, and config.

---

## Configuration at a glance

| What | Where |
|------|--------|
| Gateway (dashboard port, services, health, Docker) | `config/llmgateway.defaults.yaml` (defaults) and `config/llmgateway.yaml` (your overrides). Edit in dashboard or on disk. |
| LiteLLM (models, routing, fallbacks) | `litellm-config.yaml` at repo root. |
| API keys, provider base URLs, OAuth | `.env` (from `.env.example`). Edit in dashboard **Secrets** or on disk. |

---

## Project structure

```
LLMGateway/
├── bootstrap-llmgateway.sh      # OS prerequisites (sudo only if needed), venv, then hands off to setup; supports curl | bash
├── requirements.txt             # Python deps for management app
├── .env.example                 # Template for API keys, base URLs, OAuth (Secrets UI)
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
