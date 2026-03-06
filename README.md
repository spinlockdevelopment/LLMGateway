# LLM Gateway

A zero-custom-code LLM routing gateway for Apple Silicon. **LiteLLM Proxy** handles everything — routing, auth, spend tracking, dashboards. You just write config.

Point **Claude Code** or **Cursor** at this Mac Mini and every request routes through **OpenRouter** to **Anthropic Claude**, with **Ollama** for local inference. No custom proxy code. No Python gateway. Just LiteLLM Proxy with a good config file.

```
┌──────────────────────────────────────────────────────────────┐
│  YOUR TOOLS                                                  │
│  Claude Code ──┐                                             │
│  Cursor IDE  ──┤                                             │
│  Any OpenAI  ──┼──▶  LiteLLM Proxy   ──┬──▶ OpenRouter      │
│  SDK client  ──┤     (Docker)          │    → Anthropic Claude│
│  LangChain   ──┘     port 4000         │    → (200+ models)  │
│                                        │                      │
│                                        └──▶ Ollama            │
│                                             (bare metal,      │
│                                              Metal GPU)       │
│                                                               │
│  Observability: Prometheus + Grafana + Loki                  │
│  Data: PostgreSQL (keys, spend, models)                      │
└──────────────────────────────────────────────────────────────┘
```

## Why This Exists

You have a Mac Mini running Ollama for local models. You have an OpenRouter key for Anthropic Claude. You have Claude Code and Cursor on your dev machine. You want all of them to hit one endpoint, with routing rules, usage tracking, and cost visibility — without handing out your provider API keys.

LiteLLM Proxy does all of this out of the box. This repo is the config, Docker stack, and bootstrap tooling to get it running in minutes.

**What's in this repo (and what's not):**

| In this repo | Not in this repo |
|---|---|
| `litellm-config.yaml` — pseudo-model routing, fallbacks, provider config | Custom Python gateway code |
| `docker-compose.yml` — LiteLLM + PostgreSQL + Grafana + Prometheus + Loki | Custom admin UI |
| `bootstrap.sh` + `provision.py` — one-command Mac Mini setup | Custom routing engine |
| Grafana dashboards, Prometheus scrape config, Grafana Alloy log collection | Custom auth/rate-limit/usage tracking |

**Zero lines of custom proxy code.** LiteLLM Proxy handles routing, auth (virtual keys), rate limiting, spend tracking, the dashboard, health checks, OpenTelemetry, and both OpenAI + Anthropic API formats.

---

## Get Running in 5 Minutes

### What you need

- Mac Mini with Apple Silicon (M1/M2/M3/M4)
- An [OpenRouter API key](https://openrouter.ai/keys) — this is the only provider key required
- Docker Desktop (the bootstrap script can install this for you)

### Option A: Automated bootstrap

```bash
# Clone the repo
git clone https://github.com/<owner>/LLMGateway.git ~/src/LLMGateway
cd ~/src/LLMGateway

# Run the bootstrap (installs Python, Node, Docker, Ollama, Claude Code)
bash bootstrap.sh

# Edit your API keys
cp .env.example .env
# Set OPENROUTER_API_KEY and LITELLM_MASTER_KEY in .env

# Launch everything
bash bootstrap.sh --launch
```

The bootstrap script is idempotent — safe to run on every boot.

### Option B: Manual setup

```bash
cd ~/src/LLMGateway
cp .env.example .env
```

Edit `.env`:

```bash
OPENROUTER_API_KEY=sk-or-v1-your-key-here
LITELLM_MASTER_KEY=sk-gateway-master-change-me
```

Start Ollama (bare metal for Metal GPU):

```bash
brew install ollama
ollama serve &
ollama pull llama3.2:1b
ollama pull llama3.2:3b
```

Start the stack:

```bash
docker compose -f docker/docker-compose.yml up -d
```

Verify:

```bash
curl http://localhost:4000/health/liveliness
# {"status": "healthy"}
```

You now have:
- **LiteLLM Proxy** at `http://localhost:4000` (API endpoint)
- **LiteLLM Dashboard** at `http://localhost:4000/ui` (admin UI)
- **Grafana** at `http://localhost:3000` (observability dashboards)
- **Prometheus** at `http://localhost:9090` (metrics)
- **Ollama** at `http://localhost:11434` (local inference)

---

## Set Up Claude Code

Two environment variables:

```bash
export ANTHROPIC_BASE_URL=http://llmgateway.local:4000
export ANTHROPIC_API_KEY=sk-gateway-master-change-me
```

Or generate a dedicated virtual key for Claude Code (recommended):

```bash
curl -X POST http://localhost:4000/key/generate \
  -H "Authorization: Bearer sk-gateway-master-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "key_alias": "claude-code",
    "max_budget": 50.0,
    "budget_duration": "monthly",
    "models": ["deep-reasoning", "coding", "vision", "heartbeat"],
    "tpm_limit": 200000,
    "rpm_limit": 120
  }'
```

Use the returned key:

```bash
export ANTHROPIC_BASE_URL=http://llmgateway.local:4000
export ANTHROPIC_API_KEY=sk-<returned-key>
```

Now every Claude Code request goes through your gateway. The proxy logs it, tracks tokens and cost, and routes `deep-reasoning` and `coding` to Anthropic Claude via OpenRouter. Local tasks like `heartbeat` stay on Ollama.

## Set Up Cursor IDE

Open Cursor settings and set:

| Setting | Value |
|---------|-------|
| **API Base URL** | `http://llmgateway.local:4000/v1` |
| **API Key** | `sk-gateway-master-change-me` (or a generated virtual key) |

Generate a separate virtual key for Cursor to get independent rate limits and spend tracking:

```bash
curl -X POST http://localhost:4000/key/generate \
  -H "Authorization: Bearer sk-gateway-master-change-me" \
  -d '{"key_alias": "cursor-ide", "max_budget": 50.0, "budget_duration": "monthly"}'
```

---

## How Routing Works

Clients request **pseudo-models** — logical names like `coding` or `deep-reasoning`. LiteLLM Proxy resolves them to real provider models based on `litellm-config.yaml`.

Out of the box:

| You request | Proxy sends it to | Fallback | Why |
|---|---|---|---|
| `deep-reasoning` | **Claude Sonnet 4** via OpenRouter | Direct Anthropic API | Best reasoning model |
| `coding` | **Claude Sonnet 4** via OpenRouter | Direct Anthropic API | Best coding model |
| `vision` | **Claude Sonnet 4** via OpenRouter | GPT-4o via OpenRouter | Multimodal understanding |
| `heartbeat` | **Ollama llama3.2:1b** locally | Llama 3 via OpenRouter | Fast, free, on-device |
| `local-only` | **Ollama llama3.2:3b** locally | Ollama llama3.1:8b | Never leaves the machine |
| `cheap-research` | Round-robin: DeepSeek, Llama, Mistral via OpenRouter | — | Cost distribution |
| `budget` | Cheapest OpenRouter models | — | Highest volume, lowest cost |

Additional aliases: `claude-sonnet`, `claude-haiku`, `claude-opus`, `gpt-4o`, `deepseek`

You can also request any model directly using LiteLLM format strings:

```bash
model: "openrouter/anthropic/claude-sonnet-4"     # OpenRouter
model: "anthropic/claude-sonnet-4-20250514"        # Direct Anthropic
model: "ollama_chat/llama3.2:3b"                   # Local Ollama
model: "openai/local-model"                         # llama.cpp server
```

---

## Usage Examples

### Python — route to Anthropic Claude

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://llmgateway.local:4000/v1",
    api_key="sk-your-virtual-key",
)

# "deep-reasoning" routes to Claude Sonnet 4
response = client.chat.completions.create(
    model="deep-reasoning",
    messages=[{"role": "user", "content": "Explain quantum entanglement"}],
)
print(response.choices[0].message.content)
```

### Python — Anthropic SDK (native format)

```python
import anthropic

client = anthropic.Anthropic(
    base_url="http://llmgateway.local:4000",
    api_key="sk-your-virtual-key",
)

response = client.messages.create(
    model="coding",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Write a merge sort in Rust"}],
)
print(response.content[0].text)
```

### curl — quick test

```bash
curl -X POST http://llmgateway.local:4000/v1/chat/completions \
  -H "Authorization: Bearer sk-your-virtual-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deep-reasoning",
    "messages": [{"role": "user", "content": "What is the Riemann hypothesis?"}]
  }'
```

### curl — local Ollama (stays on device)

```bash
curl -X POST http://llmgateway.local:4000/v1/chat/completions \
  -H "Authorization: Bearer sk-your-virtual-key" \
  -d '{"model": "heartbeat", "messages": [{"role": "user", "content": "Hello!"}]}'
```

---

## LiteLLM Dashboard

LiteLLM includes a full admin dashboard at `http://localhost:4000/ui`. Log in with your `LITELLM_MASTER_KEY`.

What you can do from the dashboard:
- **Create virtual keys** — issue keys with budgets, rate limits, and model restrictions
- **Manage models** — add, edit, delete model deployments without restarting
- **Track spend** — usage breakdown by key, team, model, and provider
- **View logs** — request/response audit trail (opt-in)
- **Health monitoring** — provider and model deployment status

No custom admin UI needed.

---

## Virtual Keys (Agent Authentication)

Instead of hard-coded gateway tokens, LiteLLM uses **virtual keys** stored in PostgreSQL. Each key can have:

| Setting | Example |
|---|---|
| Budget | `$50/month` max spend |
| Rate limits | `120 rpm`, `200k tpm` |
| Model access | Only `deep-reasoning` and `coding` |
| Team | Group keys for aggregate budgets |
| Alias | Human-readable name like `claude-code` |

```bash
# Create a key for a new agent
curl -X POST http://localhost:4000/key/generate \
  -H "Authorization: Bearer sk-gateway-master-change-me" \
  -d '{
    "key_alias": "tod-agent",
    "max_budget": 10.0,
    "budget_duration": "monthly",
    "models": ["deep-reasoning", "cheap-research", "coding"],
    "rpm_limit": 60
  }'

# List all keys
curl http://localhost:4000/key/info \
  -H "Authorization: Bearer sk-gateway-master-change-me"

# Delete a key
curl -X POST http://localhost:4000/key/delete \
  -H "Authorization: Bearer sk-gateway-master-change-me" \
  -d '{"keys": ["sk-key-to-delete"]}'
```

---

## Local Models — Ollama and llama.cpp

### Ollama (default, bare metal)

Ollama runs directly on macOS for full Apple Metal GPU acceleration. **Do not run Ollama in Docker** — it loses GPU access.

```bash
brew install ollama
ollama serve &

# Pull models for the default routing config
ollama pull llama3.2:1b    # used by "heartbeat"
ollama pull llama3.2:3b    # used by "local-only"
ollama pull llama3.1:8b    # available for on-demand use
```

LiteLLM reaches Ollama via `host.docker.internal:11434` from inside Docker.

### llama.cpp (alternative)

For direct GGUF loading with fine-grained control:

```bash
brew install llama.cpp

llama-server \
  -m /models/Meta-Llama-3-8B-Instruct-Q4_K_M.gguf \
  --port 8081 -c 8192 -ngl 99 --host 127.0.0.1
```

The `llama-local` pseudo-model in `litellm-config.yaml` routes to `localhost:8081`. Start the server manually; LiteLLM connects to it as an OpenAI-compatible endpoint.

---

## Observability

### Grafana dashboards

Open `http://localhost:3000` (login: `admin` / `llmgateway`).

Pre-built panels:
- Requests per model over time
- Latency percentiles (p50/p95/p99)
- Input/output tokens per model
- Spend per API key
- Deployment failure tracking
- Latency heatmap
- Live container logs

### Prometheus metrics

LiteLLM exposes `/metrics` natively. Prometheus scrapes it directly. Key metrics:

- `litellm_requests_metric_total` — total requests by model/provider
- `litellm_spend_metric_total` — accumulated spend
- `litellm_request_total_latency_metric` — request latency histogram
- `litellm_deployment_failure_responses_total` — provider failures
- `litellm_remaining_budget_metric` — budget remaining per key

### Logs

Container logs are collected by **Grafana Alloy**, which reads from the Docker socket, parses JSON log lines for the `level` label, and ships everything to Loki. View logs in Grafana under the Loki datasource.

When external agent machines are added, run Grafana Alloy on those machines too — each Alloy instance ships directly to this stack's Loki endpoint.

---

## Bootstrap & Provisioning

The `bootstrap.sh` script automates Mac Mini setup. It installs:

| Component | Method |
|---|---|
| Xcode Command Line Tools | `xcode-select --install` |
| Homebrew | Official installer |
| Python 3.11+ | `brew install python` |
| Node.js 18+ | `brew install node` |
| Claude Code CLI | `npm install -g @anthropic-ai/claude-code` |
| Docker Desktop | `brew install --cask docker` |
| Ollama | `brew install ollama` |
| SSH | Checks/guides macOS Remote Login setup |

```bash
# First run — install everything
bash bootstrap.sh

# Subsequent runs — update everything + launch
bash bootstrap.sh --launch

# On each boot (add to Login Items or launchd)
bash bootstrap.sh --launch
```

The provisioning script (`provisioning/provision.py`) handles the detailed work. Both scripts are idempotent and log to `/tmp/llm-gateway-bootstrap.log` + macOS syslog.

---

## Configuration Reference

All configuration lives in `litellm-config.yaml`. This single file replaces the previous four YAML files.

### Adding a pseudo-model

```yaml
# In model_list:
- model_name: my-task                              # what clients request
  litellm_params:
    model: openrouter/anthropic/claude-sonnet-4    # primary
    api_key: os.environ/OPENROUTER_API_KEY
    order: 1
- model_name: my-task
  litellm_params:
    model: ollama_chat/llama3.1:8b                 # fallback
    api_base: http://host.docker.internal:11434
    order: 2
```

### Changing routing strategy

```yaml
router_settings:
  routing_strategy: least-busy     # or: simple-shuffle, latency-based-routing
```

### Setting fallback chains

```yaml
litellm_settings:
  fallbacks:
    - {"my-task": ["cheap-research"]}   # if my-task fails entirely, try cheap-research
```

### Runtime changes (no restart)

Use the LiteLLM dashboard at `/ui` or the API:

```bash
# Add a model deployment at runtime
curl -X POST http://localhost:4000/model/new \
  -H "Authorization: Bearer sk-gateway-master-change-me" \
  -d '{
    "model_name": "new-model",
    "litellm_params": {
      "model": "openrouter/openai/gpt-4o",
      "api_key": "os.environ/OPENROUTER_API_KEY"
    }
  }'
```

---

## Other Supported Providers

LiteLLM supports 100+ providers. These are **not** part of the default config — opt in by adding model deployments.

| Provider | Model format |
|---|---|
| OpenAI direct | `openai/gpt-4o` |
| Google Gemini | `gemini/gemini-2.0-flash` |
| Azure OpenAI | `azure/<deployment-name>` |
| AWS Bedrock | `bedrock/anthropic.claude-v2` |
| Mistral | `mistral/mistral-large-latest` |
| Groq | `groq/llama-3-70b` |
| Together AI | `together_ai/meta-llama/Llama-3-70b` |
| Any LiteLLM provider | [docs.litellm.ai/docs/providers](https://docs.litellm.ai/docs/providers) |

---

## Project Structure

```
LLMGateway/
├── litellm-config.yaml          # LiteLLM Proxy config (routing, models, auth, telemetry)
├── .env.example                 # API keys template
├── bootstrap.sh                 # One-command Mac Mini provisioning
├── provisioning/
│   └── provision.py             # Python provisioning (Node, Docker, Claude Code, SSH)
├── docker/
│   ├── docker-compose.yml       # LiteLLM + PostgreSQL + Grafana + Prometheus + Loki + Alloy
│   ├── prometheus/
│   │   └── prometheus.yml       # Scrape LiteLLM /metrics
│   ├── alloy/
│   │   └── alloy-config.alloy   # Docker log collection → Loki
│   └── grafana/
│       └── provisioning/
│           ├── datasources/
│           │   └── datasource.yaml
│           └── dashboards/
│               ├── dashboard.yaml
│               └── llm-gateway.json
└── README.md
```

## Future Enhancements

- **OpenRouter telemetry ingestion** — pull usage/spend data from OpenRouter's management API
- **Custom LiteLLM callbacks** — extend with project-specific logging or routing logic
- **Redis response caching** — cache identical prompts (LiteLLM has built-in support)
- **Semantic routing** — auto-classify request intent and pick the right model tier
- **GPU-aware local routing** — check Metal utilization before routing to Ollama
- **Sidecar service** — lightweight CLI for managing local model processes (Ollama, llama.cpp lifecycle)
