---
name: update-all
description: Check and apply updates for every LLM Gateway component (Open WebUI, LiteLLM, Presidio, Postgres/Redis, Hermes, llama.cpp, whisper.cpp, mlx-audio/Kokoro, Laya, Docker Desktop) with where each is pinned and how to stop/start it safely. Trigger: "update-all", "update the gateway", "check for updates".
---

# update-all

Two phases: **check** (read-only, always run first and show the table), then
**apply** only the components the user picks. One component at a time;
health-check after each (`./gw health`) before moving on.

## 1. Check: current vs latest

```bash
cd ~/src/LLMGateway; export HOMEBREW_NO_AUTO_UPDATE=1
v(){ printf '%-16s %-22s %s\n' "$1" "$2" "$3"; }
gh_latest(){ gh api repos/$1/releases/latest --jq .tag_name 2>/dev/null; }
pypi(){ curl -s https://pypi.org/pypi/$1/json | python3 -c 'import json,sys;print(json.load(sys.stdin)["info"]["version"])'; }
v open-webui  "$(docker exec open-webui sh -c 'grep -m1 \"version\" /app/package.json' | tr -dc '0-9.')" "$(gh_latest open-webui/open-webui)"
v litellm     "$(docker exec llm-gateway python -c 'import importlib.metadata as m;print(m.version("litellm"))')" "$(gh_latest BerriAI/litellm)"
v hermes      "$(git -C ~/src/hermes-agent log -1 --format='%h %cs')" "$(gh_latest NousResearch/hermes-agent)"
v llama.cpp   "$(brew list --versions llama.cpp | cut -d' ' -f2)" "$(gh_latest ggml-org/llama.cpp)"
v whisper.cpp "$(brew list --versions whisper.cpp | cut -d' ' -f2)" "$(gh_latest ggml-org/whisper.cpp)"
v mlx-audio   "$(~/.local/share/llmgateway/venv-mlx/bin/pip show mlx-audio | awk '/^Version/{print $2}')" "$(pypi mlx-audio)"
v laya        "$(~/.local/share/llmgateway/venv-laya/bin/pip show laya | awk '/^Version/{print $2}')" "$(pypi laya)"
v docker-desk "$(defaults read /Applications/Docker.app/Contents/Info.plist CFBundleShortVersionString)" "$(curl -s https://desktop.docker.com/mac/main/arm64/appcast.xml | grep -oE 'shortVersionString=\"[^\"]+' | tail -1 | cut -d'"' -f2)"
grep -nE 'image:' docker/docker-compose.yml   # postgres/redis/presidio/observability pins
```

Read release notes (`gh release view <tag> -R <repo>`) for anything with a
minor/major jump before proposing it. Report as a table, recommend, ask.

## 2. Apply, per component

Paths: compose `docker/docker-compose.yml`; host services
`config/llmgateway.defaults.yaml` (`services:`); data `/opt/storage/llmgateway`
(logs in `logs/<service>.log`); env `/opt/storage/llmgateway/.env`.

| Component | Pinned in | Update | Restart |
|---|---|---|---|
| Open WebUI | compose `open-webui` image tag | bump tag | `curl -X POST localhost:8080/ui/docker/container/open-webui/restart` (recreates with `--no-deps`) |
| LiteLLM | compose `litellm` image **digest** | `docker pull ghcr.io/berriai/litellm:v<X>` → `docker inspect --format '{{index .RepoDigests 0}}'` → paste digest | Back up DB first (below), `curl -X POST localhost:8080/ui/docker/container/llm-gateway/restart`, then `prisma db push` (below) |
| Presidio ×2 | compose digests | same digest procedure | same endpoint for `presidio-analyzer` and `presidio-anonymizer`, then test a remote route (guards fail closed) |
| Postgres / Redis | `postgres:16-alpine`, `redis:8-alpine` (floating) | `docker compose pull postgres redis` | same endpoint for `llm-postgres`, `llm-redis`. Never bump the postgres **major** without a dump/restore |
| Hermes | external: `~/src/hermes-agent` (fork, branch `test-setup`) | merge `NousResearch/hermes-agent:main`, `docker compose build gateway` there | recreate container; see Hermes below |
| llama.cpp (`local` :8082) | brew `llama.cpp` | `brew upgrade llama.cpp` | `curl -X POST localhost:8080/ui/services/local/stop` then `/start` |
| whisper.cpp (`whisper-large` :8083) | brew `whisper.cpp` | `brew upgrade whisper.cpp` | `/ui/services/whisper-large/stop`, `/start` |
| mlx-audio (`kokoro` :8880) | venv `~/.local/share/llmgateway/venv-mlx` | `…/venv-mlx/bin/pip install -U "mlx-audio[tts,stt,server]"` (+ `brew upgrade ffmpeg`) | `/ui/services/kokoro/stop`, `/start` |
| Laya (`laya` :8087) | `scripts/install-laya.sh` `VERSION=` | bump `LAYA_VERSION`, run the script | `/ui/services/laya/stop`, `/start` |
| Docker Desktop | app | Docker menu → Check for updates (GUI; can't be done from a shell) | It restarts every container; afterwards run `./gw health` |
| Gateway itself | this repo | `git pull` | `./gw restart management` |

Service list/state: `curl -s localhost:8080/api/status`. Stop/start any
gateway-managed host service via `POST /ui/services/<name>/{stop,start}`
(dashboard does the same). Prefer that to `gw stop llama-server`, which
`pkill`s **every** llama-server.

### LiteLLM DB (on every image bump)
```bash
docker exec llm-postgres sh -c 'pg_dump -U ${POSTGRES_USER:-litellm} ${POSTGRES_DB:-litellm}' > ~/.local/share/llmgateway/backups/litellm-$(date +%F).sql
# after `up -d --no-deps litellm`: startup runs `prisma migrate deploy`. Check what's left:
docker exec llm-gateway sh -c 'cd /app && prisma migrate diff --from-schema-datasource schema.prisma --to-schema-datamodel schema.prisma --script'
curl -s -o /dev/null -w '%{http_code}' -X POST localhost:4000/login -d 'username=admin&password=<master key>'   # want 303
```
Missing `LiteLLM_SpendLogs` indexes alone are harmless. Run
`prisma db push --schema /app/schema.prisma --skip-generate` only if columns
are missing or login 500s (`column ... does not exist`). That's a prod DB
write and needs explicit user OK. Never use a moving tag (`main-latest`).
After the bump, test a **streamed** remote request with a name/email (PII
unmask on streams) and a health prompt (`pii-laya` should 400). Give remote
reasoning models `max_tokens` ≥ 300, or the stream looks empty.

### Hermes
Before `docker rm`, save `docker inspect hermes-dashboard` (Env, Binds,
PortBindings, RestartPolicy). Recreate with `-it`, `HERMES_DASHBOARD=1`,
`-p 127.0.0.1:9119:9119` (loopback; tailscale serve :9443 fronts it),
`-v /Volumes/External2T/hermes-agent:/opt/data`, `--restart unless-stopped`.
Verify with `curl -u admin:<pw> localhost:9119` plus `docker logs`. "Up" alone
proves nothing because it silently exits or crash-loops.

### Hermes merge
`git -C ~/src/hermes-agent fetch upstream main` (remote `upstream` =
NousResearch). The fork's one patch makes `tts.openai.timeout` configurable;
it lives in `tools/tts_tool_openai.py`. On conflict, take upstream and re-apply
it. Tag `pre-update-<date>` before merging. Don't push without asking.

## Rules that bite
- LiteLLM config / `.env` changes: POST YAML to `/ui/litellm-config/save`.
  Never `docker compose restart`, which keeps the old env.
- `./gw restart <container>` and the endpoint above recreate (`up -d --no-deps
  --force-recreate`), so a new image or env lands. This shell can't read `.env`
  (TCC), so don't run compose `up` from it.
- `./gw restart management` only after any LiteLLM recreate has finished.
- Service binary/model path changes need `./gw restart management`.
- Local model stays Gemma-4. Upgrading llama.cpp is fine; swapping the GGUF isn't.
- After everything: `./gw health`, one chat through `local` and one remote
  route, plus STT (`transcribe`) and TTS (`speech`), then commit pin bumps.
