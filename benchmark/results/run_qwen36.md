# Run 6 — Qwen3.6-35B-A3B @ 64K ctx, phases 1–12 (B_qwen36)

Date: 2026-05-22 → 2026-05-23. Branch `test/benchmark-tinylang`. Full 12-phase run,
all phases committed (`7eed7ab..c4b5746`).

## Why this run

Qwen3.6-35B-A3B is a hybrid attention+SSM model — only ~10 of 40 layers carry a KV
cache, so allocated context is nearly free in memory pressure terms. The headroom
write-up showed 256K q8_0 fits at RSS 23.4 G / wired 26 G with `iogpu.wired_limit_mb=28000`
on the 32 GB M4. We chose **64K** rather than 256K because per-token speed is the same
regardless of allocated ctx, but a 256K KV reserves ~2.7 GiB upfront vs ~680 MiB at 64K
— and memory pressure had been the throttle in prior runs.

The plan from `SESSION_STATE.md` was: same harness/driver shape as the 16K probe,
direct on `:8083`, `tool_choice=required`, `max_tokens=4096`, per-phase commits.

## Setup

- Model: `/opt/storage/docker-models/blobs/sha256/ac0e2c1189e0...` (21 GB).
- Launch:
  ```
  llama-server -m "$MODEL" -a qwen3.6-35b-a3b --host 127.0.0.1 --port 8083 \
    --parallel 1 -c 65536 -fa on -ctk q8_0 -ctv q8_0 -ngl 999 --jinja
  ```
- Driver: `run_qwen36_1_to_12.sh` (label `B_qwen36`, suffix `_qwen36`,
  `--extra-body-json '{"tool_choice":"required"}'`, `max_tokens=4096`).
- Preflight: `iogpu.wired_limit_mb=28000`, blob present, large-write tool-call smoke
  test (4,430 chars) passed cleanly. **This smoke test was a false-positive — see
  root cause below.**

## Timing

Total wall: **8 h 42 m (31,303 s)**. Per-phase implement vs selfeval:

| phase | impl steps | impl s | impl finish | sev steps | sev s | sev finish | pytest |
|---|---|---|---|---|---|---|---|
| 01 |  9 |  273.5 | done      | 14 |  102.1 | done       | **11 / 0** |
| 02 |  4 |  778.9 | api_error | 26 | 2481.4 | api_error  | 17 / 7 |
| 03 |  4 | 1414.0 | api_error | 40 |  622.1 | step_cap   | 0 / 1 (regressed 17) |
| 04 |  3 | 1454.3 | api_error |  8 | 1308.0 | api_error  | 0 / 2 |
| 05 |  3 |  758.0 | api_error | 31 | 3425.3 | api_error  | 0 / 3 |
| 06 |  3 |  753.8 | api_error | 40 | 4184.6 | step_cap   | 0 / 4 |
| 07 |  3 |  753.2 | api_error |  5 |  744.0 | api_error  | 0 / 5 |
| 08 |  3 |  756.1 | api_error | 35 | 1654.3 | api_error  | 0 / 6 |
| 09 |  3 |  758.3 | api_error | 38 | 1655.2 | api_error  | 0 / 7 |
| 10 |  3 |  757.5 | api_error | 40 | 3319.1 | step_cap   | 0 / 8 |
| 11 |  3 | 1004.4 | api_error |  7 |  768.6 | api_error  | 0 / 9 |
| 12 |  5 |  799.1 | api_error |  7 |  768.9 | api_error  | 0 / 10 |

**Effective: 11/116** (phase 1 only). 17/24 on phase 2 was the inherited phase-1
lexer still passing; phase 2 implement crashed before changing anything.

## Root cause

A single failure class accounts for every implement crash and every selfeval crash:

```
InternalServerError: Error code: 500 -
  {'error':{'code':500,'message':'Failed to parse input at pos N','type':'server_error'}}
```

`N` clusters tightly across **all 19 failures** (11 implement + 8 selfeval):
12,572 / 12,661 / 12,674 / 12,707 / 13,038 / 13,139 / 13,207 / 13,237 / 13,270 /
13,299 / 13,422 / 13,442 / 13,446 / 13,486 / 13,723 / 13,771 / 13,832 / 13,914 / 13,946 /
14,301 / 14,422 / 14,486 / 14,685 / 14,689 / 14,720 / 14,735 / 14,774 / 15,235 / 15,269 /
15,697 / 15,781 / 16,396 / 17,196.

Range **~12.6K–17.2K bytes**, modal ~13–14K. Two error messages leak the failing byte:
`pos 13486: <` and `pos 13442: </` — the parser is choking partway through an XML-ish
closing tag in the model's output stream.

### Mechanism

1. `--jinja` makes llama-server pick `Chat format: peg-native` for qwen3.x models
   (visible in server log: `srv params_from_: Chat format: peg-native`).
2. Qwen3.6-35B-A3B is a **thinking model** — emits `<think>...</think>` before tool
   calls. Pitfall #2 (memo): `--reasoning-format deepseek` only controls *how* `<think>`
   is surfaced, not whether it's emitted.
3. With `max_tokens=4096` and ~3.5 chars/token, the model has ~14K bytes total output
   budget. Most of it goes to `<think>`, leaving the trailing tool-call XML to get cut
   off mid-tag.
4. `peg-native` does NOT tolerate truncated input — instead of returning the partial
   content with `finish_reason="length"`, it raises a 500.

This is **the same `peg-native` parser-500 failure class** that aborted the 32B run
(Run 5). The SESSION_STATE writeup correctly flagged it as an open question; the
4,430-char large-write smoke test in preflight was below the ~13K-byte threshold and
gave a false-positive.

### Why phase 1 worked

Phase 1's user prompt is just the spec and an empty workdir — the model has little to
reason over, `<think>` stays short, output fits in 14K bytes, the tool-call XML
closes cleanly. From phase 2 on the workdir carries forward phase 1's lexer.py and
the reasoning grows.

## Cascade — how 17 prior-phase tests regressed without phase 3 touching them

Phase 2 **selfeval** ran 26 steps before its own parser-500. During those 26 steps it
wrote `tinylang/ast.py` (1,635 bytes) and `tinylang/parser.py` (14,682 bytes) — partial,
unverified files left in the workdir when the 500 hit at step 27.

Those files copied forward into phase 3's seed via `prepare_phase_workdir`. Phase 3
implement crashed at step 3 without touching any file. But `tests/test_lexer.py` imports
the parser, so the broken parser.py broke lexer test collection. Pytest reported **17
regressed lexer tests** — every test that had passed at end-of-phase-1.

From there the chain was poisoned: phases 3–12 all inherited the broken parser.py,
all failed test collection, all recorded 0 passing.

So the 11 / 17 / 0 / 0 / … pass curve is **one bug + one cascade**, not 12 independent
failures. Two distinct harness/server gaps revealed:

1. `peg-native` 500s on truncated thinking-model output.
2. The harness has no rollback on selfeval crash — partial writes from a crashed
   selfeval poison the next phase's seed.

## What's saved on disk

- Per-phase commits `7eed7ab..c4b5746` (label `B_qwen36`).
- `benchmark/results/run_qwen36/phase_*.harness.log` — driver-level per-phase logs.
- `benchmark/results/transcripts/phase_*_B_implement.json`,
  `..._B_selfeval.json` — full step transcripts; api_error entries name `pos N`.
- `benchmark/results/self_eval/B_qwen36/phase_*.json` — per-phase record (impl + sev +
  final tests).
- `benchmark/results/baselines/B_qwen36/phase_*_passed.json` and `_junit.xml`.
- `benchmark/results/timings.csv` — rows with label `B_qwen36`.

## Decision for the follow-up run (B_qwen36_iter)

Drive the model with **thinking disabled** via `chat_template_kwargs.enable_thinking=false`
(passed through `--extra-body-json`). This is exactly pitfall #2's escape hatch and
frees the `max_tokens` budget for the tool-call content, which on its own is
well under the ~13K-byte peg-native threshold.

Additional changes on top:

- **`max_tokens=8192`** belt-and-suspenders for legitimately long writes late in the run.
- **Iterate selfeval on progress.** Add a `fix` subcommand to the harness so the driver
  can re-run selfeval-only on an existing workdir; the driver loops while pytest pass
  count strictly increases (bounded cap), tracks per-iteration wall time, and stops on
  no-progress.
- **Fresh workdir root** (`ModelB_qwen36_iter/`) so the prior poisoned seed cannot leak in.
- **Headless via SSH (GUI on, no user logged in)** held as the *next* fallback if these
  still hit ctx pressure on this 32 GB box.

See `run_qwen36_iter_1_to_12.sh` and the harness `fix` subcommand.
