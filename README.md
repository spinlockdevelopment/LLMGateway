# LLM Gateway

A local LLM routing gateway designed for Apple Silicon Mac Mini. Provides a unified API endpoint that transparently routes requests to local models (via Ollama/MLX) or remote providers (OpenRouter, OpenAI, Anthropic, Google).

Compatible with OpenAI and Anthropic SDKs — tools like Claude Code, Cursor, LangChain, and custom agents connect without modification.

## Architecture

```
Clients / Agents (Claude Code, Cursor, LangChain, custom)
        │
        ▼
   LLM Gateway (FastAPI + LiteLLM)
   ├── Token Auth     — gateway API tokens per agent
   ├── Routing Engine  — pseudo-model → actual model resolution
   ├── Rate Limiter    — per-agent token bucket
   └── Usage Tracker   — cost/token tracking in SQLite
        │
 ┌──────┴───────────────┐
 ▼                      ▼
Local Models         Remote APIs
(Ollama on Metal)    (OpenRouter / OpenAI / Anthropic / Google)
        │
        ▼
 OpenTelemetry Collector
        ▼
 Loki ← Promtail (logs)
 Prometheus (metrics)
        ▼
      Grafana (dashboards)
```

## Quick Start

### Prerequisites

- macOS with Apple Silicon (M1/M2/M3/M4)
- Python 3.11+
- Docker Desktop for Mac
- [Ollama](https://ollama.ai) installed on the host (bare metal, for Metal GPU acceleration)

### 1. Clone and configure

```bash
cd ~/src/LLMGateway
cp .env.example .env
```

Edit `.env` with your API keys:

```bash
OPENROUTER_API_KEY=sk-or-v1-...
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

### 2. Install Ollama and pull a model (bare metal)

Ollama runs directly on the host for Metal GPU acceleration — not in Docker.

```bash
# Install Ollama (if not already installed)
brew install ollama

# Start the Ollama server
ollama serve &

# Pull a small model for testing
ollama pull llama3.2:1b
```

### 3. Option A — Run locally (development)

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install
pip install -e .

# Run
uvicorn llm_gateway.main:app --host 0.0.0.0 --port 8000
```

### 3. Option B — Run with Docker (production)

```bash
# Start the full stack (gateway + observability)
docker compose -f docker/docker-compose.yml up -d

# View logs
docker compose -f docker/docker-compose.yml logs -f gateway
```

### 4. Verify

```bash
# Health check
curl http://localhost:8000/admin/health

# List available models
curl -H "Authorization: Bearer gw_test_token_999" \
     http://localhost:8000/v1/models
```

## Usage Examples

### OpenAI SDK (Python)

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="gw_test_token_999",  # gateway token, NOT an OpenAI key
)

# Use a pseudo-model — the gateway routes it
response = client.chat.completions.create(
    model="deep-reasoning",
    messages=[{"role": "user", "content": "Explain quantum entanglement"}],
)
print(response.choices[0].message.content)
```

### OpenAI SDK (streaming)

```python
stream = client.chat.completions.create(
    model="cheap-research",
    messages=[{"role": "user", "content": "Summarize the history of TCP/IP"}],
    stream=True,
)
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

### curl — OpenAI-compatible endpoint

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer gw_agent_tod_003" \
  -H "Content-Type: application/json" \
  -H "x-agent-name: tod" \
  -H "x-request-type: research" \
  -H "x-transaction-id: txn-001" \
  -d '{
    "model": "deep-reasoning",
    "messages": [{"role": "user", "content": "What is the Riemann hypothesis?"}]
  }'
```

### curl — Anthropic-compatible endpoint

```bash
curl -X POST http://localhost:8000/v1/messages \
  -H "Authorization: Bearer gw_test_token_999" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "coding",
    "max_tokens": 1024,
    "system": "You are a helpful coding assistant.",
    "messages": [{"role": "user", "content": "Write a Python function to merge two sorted lists"}]
  }'
```

### Direct model request (bypass routing)

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer gw_test_token_999" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "ollama_chat/llama3.2:1b",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### Claude Code configuration

Point Claude Code to the gateway:

```bash
export OPENAI_BASE_URL=http://llmgateway.local:8000/v1
export OPENAI_API_KEY=gw_claude_code_dev_001
```

### Cursor IDE configuration

In Cursor settings, set the API base URL to `http://llmgateway.local:8000/v1` and use a gateway token as the API key.

## Admin API

```bash
# Gateway status (local models + provider health)
curl http://localhost:8000/admin/status

# Usage summary (all agents)
curl -H "Authorization: Bearer gw_test_token_999" \
     http://localhost:8000/admin/usage

# Usage for a specific agent
curl -H "Authorization: Bearer gw_test_token_999" \
     "http://localhost:8000/admin/usage?agent=tod"

# List all models (pseudo + local)
curl http://localhost:8000/admin/models

# Load a local model
curl -X POST http://localhost:8000/admin/set-model \
  -H "Content-Type: application/json" \
  -d '{"model": "llama3.1-8b", "action": "load"}'

# Unload a local model
curl -X POST http://localhost:8000/admin/set-model \
  -H "Content-Type: application/json" \
  -d '{"model": "llama3.1-8b", "action": "unload"}'

# Reload all config files
curl -X POST http://localhost:8000/admin/reload-config
```

## Configuration

All configuration is in `config/` as YAML files with hot-reload support.

| File | Purpose |
|------|---------|
| `config/routing.yaml` | Pseudo-model definitions and routing strategies |
| `config/providers.yaml` | Provider-specific settings and timeouts |
| `config/agents.yaml` | Agent tokens, rate limits, and model access control |
| `config/local_models.yaml` | Local model definitions (Ollama/MLX/llama.cpp) |

### Routing strategies

- **primary/fallback** — use primary model, fall back on failure
- **local_first** — prefer local model, fall back to remote
- **round_robin** — rotate through a list of models
- **weighted** — probabilistic selection by configurable weights

### Adding a new pseudo-model

Edit `config/routing.yaml`:

```yaml
pseudo_models:
  my-new-model:
    primary: openrouter/anthropic/claude-sonnet-4
    fallback:
      - openrouter/openai/gpt-4o
```

The gateway picks up changes automatically (file watcher) or via `POST /admin/reload-config`.

### Adding a new agent

Edit `config/agents.yaml`:

```yaml
agents:
  my-agent:
    name: "My Agent"
    token: "gw_my_agent_token"
    rate_limit_rpm: 60
    allowed_models: []  # empty = all models allowed
```

## Observability

### Grafana dashboard

Open http://localhost:3000 (admin / llmgateway).

Pre-configured panels:
- Requests per model (rate)
- Latency percentiles (p50/p95/p99)
- Tokens in/out per model
- Estimated cost per agent
- Routing strategy distribution
- Live gateway logs

### Log format

All gateway logs are structured JSON:

```json
{
  "timestamp": "2025-01-15T10:30:00.000Z",
  "level": "INFO",
  "name": "llm_gateway.api.chat",
  "message": "completion",
  "agent": "tod",
  "pseudo_model": "deep-reasoning",
  "selected_model": "claude-sonnet-4",
  "provider": "openrouter",
  "tokens_in": 1200,
  "tokens_out": 340,
  "estimated_cost": 0.021,
  "latency_ms": 1850
}
```

## Mac Mini Setup Guide

### Recommended setup

1. **Ollama** — runs bare metal for Metal GPU acceleration
2. **Gateway + observability** — runs in Docker containers
3. **Network** — set a static IP or hostname (`llmgateway.local`)

### System preparation

```bash
# Set hostname (optional, for mDNS discovery)
sudo scutil --set HostName llmgateway
sudo scutil --set LocalHostName llmgateway

# Install Homebrew (if needed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Docker Desktop
brew install --cask docker

# Install Ollama
brew install ollama

# Pull models
ollama pull llama3.2:1b
ollama pull llama3.2:3b

# Start Ollama as a background service
brew services start ollama
```

### Launch the stack

```bash
cd ~/src/LLMGateway
cp .env.example .env
# Edit .env with your API keys

docker compose -f docker/docker-compose.yml up -d
```

### Verify everything is running

```bash
# Check containers
docker compose -f docker/docker-compose.yml ps

# Check Ollama
curl http://localhost:11434/api/tags

# Check gateway
curl http://localhost:8000/admin/health

# Check Grafana
open http://localhost:3000
```

## Project Structure

```
LLMGateway/
├── src/llm_gateway/
│   ├── main.py              # FastAPI app entry point
│   ├── config/
│   │   ├── loader.py        # YAML config with hot-reload
│   │   └── settings.py      # Pydantic environment settings
│   ├── routing/
│   │   ├── engine.py        # Pseudo-model routing engine
│   │   └── strategies.py    # Routing strategies
│   ├── providers/
│   │   ├── base.py          # Provider adapter interface
│   │   ├── litellm_adapter.py  # LiteLLM integration
│   │   └── registry.py      # Provider registry + health
│   ├── local/
│   │   └── manager.py       # Local model management (Ollama/MLX)
│   ├── auth/
│   │   └── tokens.py        # Gateway token auth
│   ├── tracking/
│   │   └── usage.py         # Token/cost tracking (SQLite)
│   ├── telemetry/
│   │   └── otel.py          # OpenTelemetry setup
│   ├── api/
│   │   ├── chat.py          # POST /v1/chat/completions
│   │   ├── messages.py      # POST /v1/messages
│   │   ├── models.py        # GET  /v1/models
│   │   └── admin.py         # Admin API endpoints
│   └── middleware/
│       ├── logging.py       # Structured request logging
│       └── rate_limit.py    # Token-bucket rate limiter
├── config/
│   ├── routing.yaml         # Pseudo-model routing rules
│   ├── providers.yaml       # Provider configuration
│   ├── agents.yaml          # Agent tokens and permissions
│   └── local_models.yaml    # Local model definitions
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml   # Full stack
│   ├── otel/                # OTel Collector config
│   ├── promtail/            # Promtail config
│   └── grafana/             # Grafana provisioning
├── pyproject.toml
├── .env.example
└── README.md
```

## Future Enhancements

The architecture supports these future additions:

- **Cost-optimization routing** — route to cheapest provider meeting quality threshold
- **Semantic routing** — classify request intent and route accordingly
- **Response caching** — cache identical requests (with TTL)
- **Model benchmarking** — A/B test models on same prompts
- **GPU/load-aware routing** — monitor Metal utilization, route accordingly
- **Adaptive model selection** — learn which models work best for each agent
- **Policy learning** — automatically tune routing weights based on outcomes
