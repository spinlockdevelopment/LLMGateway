# LLM Gateway — AGENTS.md

## Operating Mode
Lean and mean. Active every response.

Prose: Answer first. Use concise, active sentences and plain technical
English, broadly following ASD-STE100. Avoid filler, repetition, and
unnecessary explanation. Full sentences for explanations; fragments fine
for status. Explain in the cheapest form that lands: a sentence; a diagram
for a mechanism, flow, or structure; an HTML page for long or revisited
material. Never state the audience, level, or style; write that way.

Code — YAGNI ladder, stop at first rung that holds:
1. Speculative? Skip it, say so.  2. Already in repo? Reuse.  3. Stdlib? Use it.
4. Native platform feature? Use it.  5. Installed dep? Use it.  6. One line?
One line.  7. Else minimum new code.

Bug fix = root cause at the shared call site, not per caller.
Mark shortcuts `// lean: <ceiling>, <upgrade path>`.
Never cut: input validation at trust boundaries, error handling against data
loss, security, accessibility, anything explicitly requested.
Non-trivial logic (branch/loop/parser/money/security) leaves one runnable check.
After code: ≤3 lines — what was skipped, when to add it.

Rules below are binding: read them before acting in their area, never
re-litigate. A correction or failed approach this session becomes one new
Rule line. `/endsession` closes the session: Rules, Next, commit, push, then
ships per `## Done` when the work is complete.
History is `git log`.

## Project & Stack
One endpoint for all LLM traffic on a single 32 GB M4 Mac mini (host
`llmgateway`). LiteLLM (:4000) routes to local models and cheap remote ones;
a management service (:8080) runs the host model servers and serves the
dashboard. Clients: Open WebUI (:3001), Hermes (:9119), Claude Code and other
tools. Live and in daily use.
- Python 3.12 (management service, `gw` CLI); FastAPI + uvicorn.
- Docker Desktop + compose: LiteLLM (digest-pinned), Postgres 16, Redis 8,
  Presidio analyzer/anonymizer, Open WebUI.
- Host services from Homebrew/venvs: llama.cpp `llama-server`, whisper.cpp
  `whisper-server`, mlx-audio (Kokoro TTS), laya-serve.
- Commit format: `<area>: <summary>` (e.g. `gateway: …`, `dashboard: …`).

Routing policy:
- Everything routed through OpenRouter must be a **cheap** model; `auto`
  (OpenRouter Auto Router) and `decision` (Jev) are meta-routers. Don't add a
  premium OpenRouter route without asking.
- Premium routes are named `deep-*` (dashboard category "frontier") and call
  providers directly: `deep-reasoning` → Anthropic (`ANTHROPIC_API_KEY`),
  `deep-research` → xAI (`XAI_API_KEY`).
- Local routes may carry PII; never give one a remote fallback (the PII guard
  is skipped for local routes).
- No aliases. Local routes: `local`, `transcribe`, `speech`, `/local-decision`
  (Laya pass-through). The local model stays Gemma-4.

## Commands
```bash
./gw                                  # status of every component
./gw health                           # probe all endpoints; exit 1 if any down
./gw restart management               # after scripts/ or service-config changes
./gw logs <component>
curl -s localhost:8080/api/status     # host service states
./gw restart <host-service|container>  # containers are recreated (--no-deps --force-recreate)
python3 -c 'import json;print(json.dumps({"yaml":open("config/litellm-config.yaml").read()}))' \
  | curl -s -X POST localhost:8080/ui/litellm-config/save -H 'content-type: application/json' --data-binary @-
```
Updates: the `/update-all` skill (`.claude/skills/update-all/SKILL.md`).
No test suite; verify with `./gw health` plus one request per touched route.

## Architecture & Layout
Client → LiteLLM (:4000, PII guards on remote routes) → local servers via
`host.docker.internal` (:8082 Gemma, :8083 whisper, :8880 Kokoro, :8087 Laya)
or remote providers. The management service (launchd) starts host servers from
`config/llmgateway.defaults.yaml`, overridden by
`/opt/storage/llmgateway/config/llmgateway.yaml`.

| Path | Purpose |
|------|---------|
| `gw` | CLI: status, health, start/stop/restart, logs |
| `scripts/llmgateway.py` | Management service entry (`--install` writes the launchd plist) |
| `scripts/web/` | Dashboard API + `dashboard.html` (served fresh), LiteLLM config save |
| `scripts/services/` | llama.cpp / whisper service wrappers |
| `scripts/launchd/manager.py` | Plist generation |
| `scripts/steps/`, `setup-llmgateway.py`, `bootstrap-llmgateway.sh` | Fresh-machine setup |
| `scripts/install-laya.sh` | Laya venv install (version pin) |
| `config/litellm-config.yaml` | Bind-mounted LiteLLM config (the live one) |
| `config/guardrails/pii_guard.py` | `pii-mask` (Presidio) + `pii-laya`, mounted at `/app/pii_guard.py` |
| `config/llmgateway.defaults.yaml` | Host service definitions (binary, args, port) |
| `docker/docker-compose.yml` | Container stack and image pins |
| `.claude/skills/update-all/` | Component update procedure |

## Done
- Work on a branch; `./gw health` plus one request per touched route pass.
- Merge to `main` and push once the user says so.

## Rules
- Put installable venvs/tools on the internal disk (`~/.local/share/llmgateway/`), not `/opt/storage`. TCC blocks interactive shells there even under sudo; installs failed (laya, then mlx-audio moved to `venv-mlx`). 2026-10-07
- Apply LiteLLM config changes via `/ui/litellm-config/save`; recreate containers via `./gw restart <container>` or `POST /ui/docker/container/<name>/restart`, never `docker compose restart`. Restart keeps the old env and image, so a rotated key or bump silently never lands. 2026-10-07
- Never run `docker compose up` from an interactive shell. TCC blocks it from reading `/opt/storage/llmgateway/.env`; the management service (launchd) can, so it does every recreate. 2026-10-09
- Keep host model servers on `--host 0.0.0.0`. Docker Desktop can't reach a host port bound to 127.0.0.1 via `host.docker.internal` (tested 2026-10-09).
- Don't `./gw restart management` until a config save's LiteLLM recreate finishes. The management process runs the recreate; killing it left LiteLLM exited. 2026-09-26
- After rewriting the launchd plist, run `.venv/bin/python scripts/llmgateway.py --install`. `gw start management` only `launchctl load`s the old plist, which can point at the wrong python. 2026-05-28
- Keep launchd `StandardOut/ErrorPath` under `~/Library/Logs/`. A path under `/Volumes/*` exits 78 (EX_CONFIG) before any code runs. 2026-05-28
- Measure model memory as max(RSS, phys_footprint). MPS/Metal weights are invisible to RSS (laya-serve: 32 MB RSS vs 3.35 GB real). 2026-09-26
- Never run llama-server with `--mlock` and a large `--ctx-size` on this 32 GB box. It panicked the kernel. 2026-05-20
- Keep Open WebUI tag/follow-up generation off and `local` at `timeout: 600` with no timeout retries. With `--parallel 1`, background tasks queued ahead of the reply; 120 s timeouts + retries returned 408 and chats showed nothing. 2026-10-07
- Re-declare every hook a LiteLLM guardrail subclass needs in its own class body. LiteLLM dispatches from the leaf class `__dict__`; inherited Presidio hooks were silently skipped (streams stayed masked). 2026-09-26
- Don't ask Laya "is there PII?" on masked text. It flags `<PERSON_1>` placeholders at 0.97; targeted health/finance questions separate cleanly. 2026-09-26
- Don't propose swapping the local model off Gemma or re-running the Gemma vs Qwen A/B. User closed it. 2026-09-26
- Keep dashboard rows minimal: no explanatory subtitle lines beyond "↳ fallback:". User removed them as noise. 2026-09-26
- Push to the default branch only after the user says so in their own words. The auto-mode classifier blocks pushes authorized only by agent-written task text. 2026-06-23
- Checkpoint each phase of a long multi-step run as its own commit on a test branch. One slow phase blocked the rest and a crash lost work. 2026-05-19

## Next
Add `ANTHROPIC_API_KEY` and `XAI_API_KEY` on the Secrets page to activate
`deep-reasoning` and `deep-research`.
- P1 — Update Docker Desktop 4.90 → 4.94 from its menu (restarts all containers), then `./gw health`.
- P1 — Log in to Hermes at :9443; if fine, `docker rm hermes-dashboard-old`, push `~/src/hermes-agent` branch `test-setup`, then `docker image prune -a && docker builder prune` (~60 GB).
- P1 — LAN exposure: LiteLLM :4000 uses the default master key `sk-gateway-master-change-me`, and Open WebUI :3001 runs `WEBUI_AUTH=false`, both on 0.0.0.0. Rotate the key (update Open WebUI, Hermes, clients) or publish both on 127.0.0.1 (tailnet `serve` still works).
- P2 — Point Open WebUI STT/TTS at LiteLLM `transcribe` / `speech` (compose `AUDIO_*`: base `http://litellm:4000/v1`, a virtual key); also set it in Admin → Audio, which overrides env.
- P2 — More Laya guard questions: prompt-injection, secrets. Street addresses are an open PII gap.
- P3 — Dead features (declined 2026-10-09; ask first): observability profile, DMR/llmfit Models tabs, `whisper-fast`, mutex groups, `benchmark/` on main, one-off setup scripts.
- P3 — Setup doesn't install venv-mlx, Laya, the GGUF, `tailscale serve` or Hermes (see README).

## Notes & Pointers
- History: `git log`, not this file.
- Data dir `/opt/storage/llmgateway` (symlink to `/Volumes/External2T`): `.env`, docker volumes, service logs in `logs/<service>.log`, user config override. Survives an OS wipe. Interactive shells can't write it (TCC); the launchd job can.
- The local GGUF path lives in the user override `/opt/storage/llmgateway/config/llmgateway.yaml`; changing it needs `./gw restart management`. Unused `Qwen3.6-35B-A3B-UD-Q4_K_M.gguf` (22 GB) is on disk; delete only if asked.
- Memory: with every service up, ~2 GB is available of 32 GB (2026-10-09); Gemma-4-26B-A4B at 128K q8_0 KV is ~18 GB. Measure before adding a model.
- Hermes is built from `~/src/hermes-agent` (fork, branch `test-setup`), not this repo; recreate steps are in the update-all skill.
- Tailnet HTTPS: :443 LiteLLM, :8443 Open WebUI (mic needs HTTPS), :8444 dashboard, :9443 Hermes.
- OrbStack was A/B tested 2026-06-23: ~1 GB lighter, drop-in compatible, not adopted.
- tinylang coding benchmark: branch `test/benchmark-tinylang`; read `benchmark/SESSION_STATE.md` first.
