# Run 5b — Qwen2.5-Coder-32B @ 16K ctx, phases 1–3 timing probe (B_32bcoder16k)

Date: 2026-05-20/21. Branch `test/benchmark-tinylang`. Probe only — not a full run.

## Why

Run 5 (32K) was aborted at phase 9 after ~15 h: `peg-native` tool-call 500s on large
`write_file` content + 32K KV thrash on the 32 GB box (per-phase time 14 min → 4.8 h).
This probe re-ran **phases 1–3 only at `-c 16384`** to measure whether smaller ctx makes
the box usably fast. Server flags identical to Run 5 except `-c 16384`.

## Timing (vs the 32K run's phases 1–3)

| phase | 16K | 32K | passed/failed (16K) | finish (16K) |
|---|---|---|---|---|
| 01 | 12 min (717s) | 14 min (841s) | 2 / 9 | done |
| 02 | 32 min (1912s) | 45 min (2729s) | 3 / 21 | step_cap |
| 03 | 37 min (2227s) | 42 min (2505s) | 6 / 33 | **api_error** |
| **total** | **81 min** | ~101 min | | |

~20% faster at 16K. Memory healthy throughout: wired ~22 GiB, compressor ~170 MB
(vs 4.8 GB late in the 32K run) — **no KV/memory thrash at 16K**. **Zero `peg-native`
500s** this probe.

## Key finding: 16K is too small for this harness's context accumulation

Phase 3's `api_error` was NOT a tool-call 500 (there were none). It was a context overflow:

```
srv send_error: request (16718 tokens) exceeds the available context size (16384 tokens),
                try increasing it
```

The harness agent loop accumulates system prompt + full phase spec + every tool output
across 33–80 steps. By phase 3 that crossed 16,384 tokens and the request errored. So:

- **32K**: context fits, but KV thrashes + memory compresses → 2–5 h/phase late, plus
  `peg-native` 500s on big writes.
- **16K**: fast, no thrash, no 500s in p1–3 — but the conversation overflows the window
  by phase 3.

Neither size is right on a 32 GB box. The lever is **the harness's context size per
phase**, not just the server `-c`. Pass counts ticked up vs 32K (P2 0→3, P3 0→6) but
aren't cleanly comparable (32K P3 errored during pytest collection).

## Verdict

A bigger ctx isn't the fix and a smaller ctx isn't either. Two real fixes:
1. **Trim the harness context** — truncate/summarize old tool outputs instead of keeping
   them verbatim. Addresses both overflow (16K) and thrash (32K) at once.
2. **Headless macOS boot** (no GUI/Docker, only llama-server) to afford 32K KV without
   compression — see [[project_tinylang_bench_headless_option]]. This is the chosen
   direction (see SESSION_STATE "Forward plan").

## Artifacts

- Commits `bcf5484`/`973ab2c`/`4bb03ca` (phases 1–3) + `7f297c8` (driver) on
  `test/benchmark-tinylang`.
- Workdirs `benchmark/ModelB_32bcoder16k/phase_0{1,2,3}/`, driver
  `run_32bcoder16k_1_to_3.sh`, logs `results/run_32bcoder16k/`.
