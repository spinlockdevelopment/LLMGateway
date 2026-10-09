# LLM Gateway

One OpenAI-compatible endpoint for all LLM traffic on a single 32 GB M4 Mac
mini. LiteLLM (:4000) routes each request to a local model on the host or to
a cheap remote one. A management service (:8080) runs the host model servers
and serves the dashboard.

```
client ─▶ LiteLLM :4000 ─┬─▶ host.docker.internal: Gemma :8082 · whisper :8083
          (PII guards on │                         Kokoro :8880 · Laya :8087
           remote routes)└─▶ OpenRouter · Anthropic · xAI
```

## Routes

| Route | Backend | Notes |
|---|---|---|
| `local` | Gemma-4-26B-A4B on llama-server :8082 | May carry PII; never has a remote fallback |
| `transcribe` | whisper.cpp :8083 | `/v1/audio/transcriptions` |
| `speech` | Kokoro (mlx-audio) :8880 | `/v1/audio/speech` |
| `/local-decision` | Laya :8087 | Pass-through: `POST /local-decision/v1/systemone` |
| `coding`, `reasoning`, `research` | OpenRouter (cheap models, load-balanced) | |
| `decision`, `auto` | OpenRouter meta-routers (Jev, Auto Router) | `auto` can land on premium models |
| `deep-reasoning` | Anthropic direct | Needs `ANTHROPIC_API_KEY` |
| `deep-research` | xAI direct | Needs `XAI_API_KEY` |

Remote routes pass two guards from `config/guardrails/pii_guard.py`:
`pii-mask` (Presidio masks names, emails, IDs and card numbers) and `pii-laya`
(blocks text that still reveals someone's health or finances). Both fail
closed. Local routes skip them.

## Connect a client

```bash
curl http://<host>:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_KEY" -H 'content-type: application/json' \
  -d '{"model":"local","messages":[{"role":"user","content":"hi"}]}'
```

Base URL `http://<host>:4000/v1`. The key is `LITELLM_MASTER_KEY` from `.env`
or a virtual key made in the LiteLLM UI (`/ui`). On the tailnet, use HTTPS:
:443 LiteLLM, :8443 Open WebUI, :8444 dashboard, :9443 Hermes.

## Components

- **Docker** (`docker/docker-compose.yml`): LiteLLM (digest-pinned), Postgres 16
  (keys, spend), Redis 8 (cache), Presidio analyzer + anonymizer, Open WebUI
  (:3001). Prometheus/Grafana/Loki/Alloy sit behind the opt-in `observability`
  profile and are off.
- **Host** (`config/llmgateway.defaults.yaml`, user override in
  `/opt/storage/llmgateway/config/llmgateway.yaml`): llama-server, whisper-server,
  mlx-audio, laya-serve. The management service (launchd) starts and supervises
  them.
- **Data** `/opt/storage/llmgateway`: `.env`, Docker volumes, service logs in
  `logs/<service>.log`. The management log is `~/Library/Logs/llm-gateway/gateway.log`.

## Operate

```bash
./gw                          # status of every component
./gw health                   # probe all endpoints; exit 1 if any down
./gw start|stop|restart <c>   # host service (local, kokoro…), container, docker, management
./gw logs <c>
```

Container restarts recreate the container, so `.env` and image changes land.
Edit routes on the dashboard (or POST to `/ui/litellm-config/save`); that
recreates LiteLLM. Updates: `.claude/skills/update-all/SKILL.md`.

## Fresh machine

```bash
curl -fsSL https://raw.githubusercontent.com/spinlockdevelopment/LLMGateway/main/bootstrap-llmgateway.sh | bash
```

The bootstrap installs Homebrew, git, Python, Docker Desktop and the repo venv,
then runs `scripts/setup-llmgateway.py`. Setup writes `.env`, starts the Docker
stack, installs llama.cpp/whisper.cpp from Homebrew and registers the launchd
service.

Setup does **not** reproduce the full live host. Do these by hand:

- **mlx-audio venv** (Kokoro): `~/.local/share/llmgateway/venv-mlx`,
  `pip install "mlx-audio[tts,stt,server]"`.
- **Laya**: `scripts/install-laya.sh`.
- **Model files**: the Gemma GGUF and whisper model under `/opt/storage`; set
  their paths in the user override.
- **Tailnet HTTPS**: `tailscale serve` for the four ports above.
- **Hermes**: built from `~/src/hermes-agent`; see the update-all skill.
