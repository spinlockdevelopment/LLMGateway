# Dashboard Improvements (Follow-up)

These are post-install-simplification improvements to tackle separately.

1. **Model pull progress** — Show real-time streaming output when pulling Docker Model Runner models (currently fire-and-forget)
2. **litellm-config.yaml editor** — Add/remove model routes from the web UI instead of editing YAML manually
3. **Observability toggle** — Enable/disable the observability stack from the dashboard without re-running setup
4. **Unified status page** — Move `gw status` output into a dashboard tab with auto-refresh
5. **Whisper controls** — Start/stop whisper + upload audio for test transcription from dashboard
6. **Component installer** — Install optional components (whisper, llmfit, observability) from dashboard post-setup
