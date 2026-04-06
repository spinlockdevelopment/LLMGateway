# LLM Gateway

A single place to send all your LLM traffic on an Apple Silicon Mac. **LiteLLM Proxy** does the routing, auth, and spend tracking; a small **management interface** gives you a local dashboard with config editor and control over local services. Point Claude Code, Cursor, Agents or any compatible client at one endpoint to route to local models or your cloud subscriptions (e.g. Claude, OpenAI, Gemini, OpenRouter).

---

## Architecture

```
                    Tools / Agents
         Claude Code · Cursor · OpenClaw · (etc)
                              |
                              v
+-----------------------------------------------------------------------------+
|  YOUR MACHINE                                                               |
|                                                                             |
|  +----------------------+ +----------------------+ +----------------------+ |
|  |  Management svc      | |  LiteLLM Proxy       | |  Observability       | |
|  |  port 8080           | |  port 4000           | |  (optional)          | |
|  +----------+-----------+ +----------+-----------+ +----------+-----------+ |
|             |                        |                        |             |
|             +------------------------+------------------------+             |
|                                                                             |
|                Docker stack (core: LiteLLM + PostgreSQL)                    |
|                + optional: Grafana, Prometheus, Loki, Alloy                 |
|                                      |                                      |
|                                      |                                      |
|             LiteLLM Proxy -----------+----------> Docker Model Runner        |
|                 |                                 (local models, port 12434) |
|                 |                                                           |
+-----------------|-----------------------------------------------------------+
                  |
                  v
                  Cloud Services
         Claude · OpenAI · OpenRouter · (etc)
```

- **Tools/agents** (e.g. Claude Code, Cursor) send requests to **LiteLLM Proxy** at `http://<this-mac>:4000`.
- **LiteLLM** routes traffic to **cloud services** (OpenRouter, Anthropic, etc.) and **local models** via Docker Model Runner.
- **Observability** (Grafana, Prometheus, Loki) is optional — enable during setup if you want dashboards and metrics.

---

## Prerequisites

Install these before running setup:

| Prerequisite | Install |
|---|---|
| **Python 3.11+** | `brew install python@3.12` or [python.org](https://www.python.org/downloads/) |
| **Docker Desktop** | `brew install --cask docker` or [docker.com](https://docker.com/products/docker-desktop/) |
| **Git** | `brew install git` or included with Xcode Command Line Tools |

---

## Get running

### 1. Clone and run setup

```bash
git clone https://github.com/spinlockdevelopment/LLMGateway.git ~/src/LLMGateway
cd ~/src/LLMGateway
python3 scripts/setup-llmgateway.py
```

The setup script:
- Creates a Python virtual environment (`.venv`) and installs dependencies
- Asks you to choose optional components (observability, whisper, llmfit)
- Launches the Docker stack (LiteLLM + PostgreSQL, plus observability if selected)
- Enables Docker Model Runner for local model inference
- Installs the management console as a launchd agent (auto-starts on login)

> No `sudo` required. The script is safe to re-run — all steps are idempotent.

To check status without making changes:

```bash
python3 scripts/setup-llmgateway.py --status
```

### 2. Add your API keys

Use the dashboard **Secrets** tab (http://localhost:8080) to edit `.env`, or edit by hand:

```bash
# Edit ~/.llm-gateway/.env
# Set any API keys you need; LITELLM_MASTER_KEY is used for the proxy UI and virtual keys
```

### 3. Verify

- **Management dashboard:** http://localhost:8080
- **LiteLLM Proxy:** http://localhost:4000/health/liveliness
- **LiteLLM UI:** http://localhost:4000/ui (login with `LITELLM_MASTER_KEY`)

---

## Commands

**Setup:**

| Command | Effect |
|---------|--------|
| `python3 scripts/setup-llmgateway.py` | Full setup (creates venv, provisions stack). Safe to re-run. |
| `python3 scripts/setup-llmgateway.py --status` | Status check only (no changes). |
| `python3 scripts/setup-llmgateway.py --verbose` | Setup with debug-level output. |

**Day-to-day (`gw` helper):**

| Command | Effect |
|---------|--------|
| `./gw` | Show status of all components and key paths. |
| `./gw start <component>` | Start a component. |
| `./gw stop <component>` | Stop a component. |
| `./gw restart <component>` | Restart a component. |
| `./gw logs <component>` | Tail logs for a component. |
| `./gw uninstall` | Deregister autostart, stop all services. |

Components: `management`, `docker`, `litellm`, `postgres`, `whisper-server`, `grafana`, `prometheus`, `loki`, `alloy` (last four only if observability is enabled).

---

## Using the dashboard

Open **http://localhost:8080**.

- **Dashboard** — System overview, component status, Docker Model Runner models.
- **Models** — Pull/remove local models via Docker Model Runner, discover models via llmfit.
- **Config** — Edit gateway settings. Stored in `~/.llm-gateway/config/llmgateway.yaml`.
- **Secrets** — Edit `.env`: API keys, provider base URLs. Saving restarts LiteLLM if relevant keys changed.

LiteLLM's own UI (keys, spend, models) is at **http://localhost:4000/ui** (use `LITELLM_MASTER_KEY`).

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

---

## How routing works

Clients send requests to LiteLLM with a **model name**. LiteLLM maps that to real backends using `litellm-config.yaml`.

| You request | Routed to (default) |
|-------------|----------------------|
| `deep-reasoning` | Claude Sonnet 4 (OpenRouter or direct Anthropic) |
| `coding` | Claude Sonnet 4 (OpenRouter or direct Anthropic) |
| `vision` | Claude Sonnet 4 (OpenRouter) |
| `heartbeat` | Docker Model Runner (llama3.2:1b) — local |
| `local-only` | Docker Model Runner (qwen2.5-coder:7b) — local |
| Others | See `litellm-config.yaml` (e.g. `cheap-research`, `budget`) |

Edit `litellm-config.yaml` and restart the LiteLLM container to change routing. You can also add models at runtime via the LiteLLM UI or API.

---

## Configuration

| What | Where |
|------|--------|
| Gateway config + install choices | `~/.llm-gateway/config/llmgateway.yaml` (edit in dashboard or on disk) |
| LiteLLM model routing | `litellm-config.yaml` at repo root |
| API keys, provider base URLs | `~/.llm-gateway/.env` (edit in dashboard Secrets or on disk) |

---

## Project structure

```
LLMGateway/
├── requirements.txt             # Python deps for management app
├── .env.example                 # Template for API keys, base URLs
├── litellm-config.yaml          # LiteLLM Proxy: routing, models, providers
├── gw                           # CLI helper: status, start, stop, logs
├── scripts/
│   ├── llmgateway.py            # Management app: web UI, service manager, launchd
│   ├── setup-llmgateway.py      # Setup: self-bootstrapping, provisions everything
│   ├── config/                  # Config load/save/validate
│   ├── launchd/                 # macOS launchd install/uninstall
│   ├── services/                # Docker Model Runner, Whisper, llmfit wrappers
│   ├── steps/                   # Provisioning steps (Docker, .env, DMR, llmfit)
│   └── web/                     # Dashboard HTML, API, UI routes
├── docker/
│   ├── docker-compose.yml               # Core stack: LiteLLM + PostgreSQL
│   ├── docker-compose.observability.yml # Optional: Grafana, Prometheus, Loki, Alloy
│   ├── prometheus/
│   ├── alloy/
│   └── grafana/
└── tests/
```

---

## Virtual keys and observability

**Virtual keys** — In LiteLLM UI (http://localhost:4000/ui) you can create keys with budgets, rate limits, and model restrictions.

**Observability** — If enabled during setup: Grafana at http://localhost:3000 (default login `admin` / `llmgateway`), Prometheus at http://localhost:9090. Enable later by re-running `python3 scripts/setup-llmgateway.py` and selecting the observability option.

---

## Optional: Whisper speech-to-text

During setup you can enable whisper-server for speech-to-text. If you skipped it:

```bash
brew install whisper-cpp
./gw start whisper-server
```

Or re-run setup and toggle the whisper option.

---

## Permissions after git pull

Scripts are committed with the executable bit set. If `./gw` fails with "Permission denied":

```bash
chmod +x gw scripts/setup-llmgateway.py scripts/llmgateway.py
```
