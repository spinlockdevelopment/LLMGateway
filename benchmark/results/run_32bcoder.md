# Run 5 — Qwen2.5-Coder-32B-Instruct (B_32bcoder) — ABORTED at phase 9

Date: 2026-05-20. Branch `test/benchmark-tinylang`.

## One-liner

Qwen2.5-Coder-32B-Instruct Q4_K_M was **aborted at phase 9 of 12 after ~15 h wall**.
Unlike the 14B (which stubbed-and-quit), the 32B *engages* substantively — it hits the
80-step implement cap writing real code — but two compounding problems made the run
worthless and impractically slow: (1) `llama-server`'s `peg-native` tool-call parser
returns **HTTP 500 on `write_file` calls with large `content`**, so the model's actual
file writes are dropped server-side; and (2) the 32K KV cache thrashes on the 32 GB box,
and memory-compression pressure dragged per-phase time from ~14 min (phase 1) to ~4.8 h
(phase 8). Aborted on the `peg-native`-500 diagnosis with 8 phases committed.

## Setup

| field | value |
|---|---|
| model | `Qwen2.5-Coder-32B-Instruct-Q4_K_M.gguf` (19.85 GB / 18 GiB), `docker model pull hf.co/bartowski/Qwen2.5-Coder-32B-Instruct-GGUF:Q4_K_M` |
| model store | relocated to **2 TB external `/opt/storage/docker-models`** (`~/.docker/models` symlink) — see `project_docker_store_opt_storage` memory |
| server | `llama-server` on :8083, `-c 32768`, `-fa on`, `-ctk/-ctv q4_0`, `-ngl 999`, `--jinja`, **no `--mlock`**, no `--reasoning-format` |
| tool_choice | `"required"` via `--extra-body-json` |
| MAX_TOKENS | 4096 |
| label / workdir | `B_32bcoder` / `ModelB_32bcoder/phase_NN/` |
| memory | RSS 20.5 GB, **wired ~23 GiB** (edge of the <24 GiB ceiling); compressor climbed 1 GB → 4.8 GB over the run |
| containers | LiteLLM + Postgres stopped mid-run (benchmark bypasses LiteLLM); did not affect anything |

Smoke test (`tool_choice=required`, small `ls` call) passed clean before the run — the
500s only appear once `write_file` content gets large.

## Per-phase tallies (phases 01–08 committed; 09 partial, not committed)

| phase | passed / failed | implement (steps, s) | self-eval (steps, s) | phase wall |
|---|---|---|---|---|
| 01 | **2** / 9 | 6, 334s, done | 24, 507s, done | 841s (14 min) |
| 02 | 0 / 1 | 80, 2673s, **step_cap** | 2, 55s, done | 2729s (45 min) |
| 03 | 0 / 2 | 80, 2456s, **step_cap** | 2, 48s, done | 2505s (42 min) |
| 04 | **8** / 39 | 80, 2014s, **step_cap** | 40, 769s, step_cap | 2784s (46 min) |
| 05 | 0 / 1 | 64, 6297s, **api_error** | 40, 1845s, step_cap | 8143s (2.3 h) |
| 06 | 0 / 6 | 49, 6994s, **api_error** | 40, 1160s, step_cap | 8154s (2.3 h) |
| 07 | 0 / 6 | 80, 2051s, **step_cap** | 22, 1423s, done | 3474s (58 min) |
| 08 | 0 / 2 | 41, 7713s, **api_error** | 39, 9596s, **api_error** | 17310s (4.8 h) |
| 09 | — | 40, 7513s, **api_error** | (killed mid self-eval) | aborted |

Through phase 8: **~12.8 h wall**, peak phase 4 with 8 passes. Total elapsed at abort
~14.9 h. `peg-native` 500s logged: 15+.

## The two failures

### 1. `peg-native` 500 on large tool-call content (fatal to results)

`llama-server` (llama.cpp build 8240, `Chat format: peg-native`) raises:

```
got exception: {"error":{"code":500,"message":"Failed to parse input at pos 12:
  {\"name\": \"write_file\", \"arguments\": {\"content\": \"from tinylang.ast import ...
  <a full multi-line Python module with escaped quotes/regex>"}}
```

The constrained-grammar / PEG parser fails on the `write_file` call once `content` is a
real source file (escaped newlines, nested quotes, regex backslashes). The request 500s,
the harness records `finish=api_error`, and the file the model meant to write never
lands. So even when the 32B writes substantive code, it doesn't reach disk → ~0 passes.
This is the same *class* of tool-call-parsing fragility seen before, but a different
trigger than the 14B's (14B never wrote enough to hit it; 32B does).

### 2. KV thrash + memory compression → catastrophic slowdown

`decode: failed to find a memory slot for batch of size 2048` / `failed to find free
space in the KV cache, retrying with smaller batch size`. At 32K ctx with q4_0 KV on a
32 GB box, as context fills the slot thrashes; combined with system memory-compression
(compressor 1 GB → 4.8 GB), per-step time grew ~4–5× from early to late phases
(~45 s/step → ~190–250 s/step). This is why phase 8 took 4.8 h.

## Comparison across runs (full 12 phases unless noted)

| run | model | passed / 116 | wall | note |
|---|---|---|---|---|
| Run 3 `A_subagent` | Sonnet 4 (Claude Code subagent) | **116 / 116** | 52.8 min | done |
| Run 2 `B_capped` | qwen3-coder-30B-A3B Q4_K_M | **23 / 116** | 4 h 17 min | Phase 04/10 deliverable bugs |
| Run 4 `B_14bcoder` | Qwen2.5-Coder-14B Q4_K_M | **0 / 116** | 29 min | stub-and-done |
| Run 5 `B_32bcoder` (this) | Qwen2.5-Coder-32B Q4_K_M | **~10 / 116** thru ph8, then aborted | ~15 h to ph9 | peg-native 500s + KV thrash |
| Run 4a `B_14b` (aborted) | qwen3-14b base Q4_K_M | 0 / 11 (ph1) | 51 min | api_error |

The 32B is the first local model that *tries* (hits step caps, writes real modules,
peak 8 passes in phase 4) rather than stubbing out. But the tool-call path drops its big
writes and the memory ceiling makes 32K ctx unworkable. This run does **not** cleanly
test the context-degradation hypothesis — it was killed by infrastructure, not capability.

## What to try next (if pursued)

1. **Drop `--ctx-size` to 16384 (or less).** Stops the KV thrash that caused most of the
   slowdown; the phases that fit show ~45 s/step, ~10× faster.
2. **Fix the tool-call format for large content.** The `peg-native` parser is the
   blocker. Options: a different `--chat-template`/tool-call grammar, route writes
   through a `run_bash` heredoc instead of `write_file`, or chunk large writes.
3. **Headless macOS boot + SSH, no Docker, only llama-server** — reclaims the wired RAM
   that's forcing compression at 23 GiB (see `project_tinylang_bench_headless_option`).
4. Re-run only after 1+2; otherwise it's another ~15 h of `api_error`.

## Artifacts

- Per-phase commits: `b16ebf4` (phase 01) … `e9554bf` (phase 08), 8 commits on
  `test/benchmark-tinylang`. Phase 09 partial committed separately as aborted.
- Workdirs: `benchmark/ModelB_32bcoder/phase_NN/`
- Junit + passed.json: `benchmark/results/baselines/B_32bcoder/`
- Per-phase harness logs: `benchmark/results/run_32bcoder/phase_NN.harness.log`
- Driver log: `benchmark/results/run_32bcoder/driver.log`
- Server log (with the 500 exceptions): `benchmark/results/run_32bcoder/llama-server.log`
