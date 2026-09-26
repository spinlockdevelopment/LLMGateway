# LLM Gateway — notes for Claude

## Layout that bites

- `config/litellm-config.yaml` is the file docker-compose bind-mounts into
  the LiteLLM container. The dashboard's save endpoint also mirrors it to
  `/opt/storage/llmgateway/litellm-config.yaml`; that copy is a backup only.
- Apply a LiteLLM config or `.env` change by POSTing the YAML to
  `http://localhost:8080/ui/litellm-config/save` (or saving in the
  dashboard). It force-recreates the container; `docker compose restart`
  does not re-read `.env`.
- `/opt/storage` is TCC-protected: interactive shells (even `sudo`) can't
  write there. The gateway's launchd job can, so services that need to
  write there (HF downloads) must do it themselves.
- Gateway code changes (`scripts/`) need `./gw restart management`;
  `dashboard.html` is served fresh.

## Routing policy

- Everything routed through OpenRouter must be a **cheap** model. The one
  deliberate exception is `deep-reasoning` (Opus 5.5). Don't add another
  premium OpenRouter route without asking.
- Premium routes are named `deep-*` (dashboard category "frontier");
  `deep-research` calls xAI directly (`XAI_API_KEY`).
- No aliases. Local routes: `local`, `transcribe`, `speech`,
  `/local-decision` (Laya pass-through). The local model stays Gemma-4;
  don't propose swapping it.

## Rules

- Put installable venvs/tools on the internal disk (`~/.local/share/llmgateway/`), not `/opt/storage`. TCC blocks interactive shells there even under sudo; the install failed. 2026-09-26
- Apply LiteLLM config/.env changes via `/ui/litellm-config/save`, never `docker compose restart`. Restart keeps the old env, so a rotated key silently never lands. 2026-09-26
- Measure model memory as max(RSS, phys_footprint). MPS/Metal weights are invisible to RSS (laya-serve: 32 MB RSS vs 3.35 GB real). 2026-09-26
- Keep dashboard rows minimal: no explanatory subtitle lines beyond "↳ fallback:". User removed them as noise. 2026-09-26
- Don't propose swapping the local model off Gemma or re-running the Gemma vs Qwen A/B. User closed it. 2026-09-26

## Next

- Push `761983a` to main (committed locally, not pushed), then add `XAI_API_KEY` on the Secrets page to activate `deep-research`.

## Todo

- [ ] **`embed` route.** Local `llama-server --embedding` (e.g.
      Qwen3-Embedding-0.6B GGUF, ~0.6 GB) as a new gateway service, or
      OpenRouter `voyageai/voyage-4-lite` ($0.02/M). Local keeps documents
      on the box. Measure memory before enabling (Models bucket ~20.5 GB of 32).
- [ ] **`rerank` route.** Local `llama-server --reranking` with
      bge-reranker-v2-m3 GGUF (~0.6 GB); LiteLLM exposes `/v1/rerank`.
- [ ] **`image` route.** OpenRouter `google/gemini-3.1-flash-lite-image`
      ($0.25/M in) via `/v1/images/generations` (cheap, fits the policy).
- [ ] **MCP gateway in LiteLLM** (`mcp_servers:`), one tool hub for all
      clients/Hermes: start with fetch/crawl (URL → markdown; Firecrawl is
      supported), GitHub; later filesystem/git (scoped) and Playwright.
- [ ] **Laya as a guardrail.** LiteLLM custom guardrail that asks
      `/local-decision` (~70 ms) for prompt-injection / secrets / PII
      probabilities before the paid routes, blocking above a threshold.
- [ ] Optional: `/v1/ocr` (needs a Mistral key) and `/v1/vector_stores`
      (only after `embed`). Low priority; vision models + Open WebUI cover them.
- [ ] Point Open WebUI's STT/TTS at LiteLLM `transcribe` / `speech`
      instead of calling :8083 / :8880 directly (keys + spend logging).
