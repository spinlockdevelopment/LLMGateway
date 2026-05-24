# Consolidated benchmark results — 2026-05-24

Snapshot taken mid-flight: the Gemma-4-26B-A4B run is at **phase 10/12 in progress**;
**phases 1–9 are committed**. This doc rolls up everything done in the last 3 days
(Runs 6, 7, 8 of the benchmark) plus the older baselines/runs for comparison.

## Headline

**Gemma-4-26B-A4B Q4_K_M @ 64K is by a wide margin the best local model the
benchmark has ever seen on this hardware.** Through phase 9 it matches Sonnet
exactly on phases 1, 3, 4, 5, 6, 7 (six of nine phases at 100%) and is at **83 of
the 92 cumulative tests** (~90%) at end-of-phase-9. The previous local-model
ceiling was Qwen2.5-Coder-32B aborting at phase 9 with ~peak 8 passes and
ultimately 0/116 effective; everything else hit ≤25 of 116.

## Side-by-side: per-phase passing tests vs Sonnet baseline

The benchmark's `tests/` is cumulative — each phase drops a new batch of tests on
top of the prior ones. So the "expected" pass count grows monotonically. Sonnet
hits the expected count at every phase.

| phase | Sonnet (A_subagent) | **Gemma-4 26B-A4B** | qwen3.6 (B_qwen36) | qwen3.6-iter (B_qwen36_iter) | qwen2.5-coder-32b (B_32bcoder) |
|---:|---:|---:|---:|---:|---:|
| 01 |  11 / 11 | **11 / 11** ✓ | 11 / 0 ✓  | 11 / 0 ✓  | 2 / 9 |
| 02 |  24 / 24 | **12 / 12**   | 17 / 7    | 0 / 1     | 3 / 21 |
| 03 |  39 / 39 | **39 / 39** ✓ | 0 / 1     | 0 / 2     | 6 / 33 |
| 04 |  47 / 47 | **47 / 47** ✓ | 0 / 2     | 0 / 3     | (peak 8 here) |
| 05 |  55 / 55 | **55 / 55** ✓ | 0 / 3     | 0 / 4     | … |
| 06 |  65 / 65 | **65 / 65** ✓ | 0 / 4     | 0 / 5     | … |
| 07 |  71 / 71 | **71 / 71** ✓ | 0 / 5     | 0 / 6     | … |
| 08 |  82 / 82 | **78 / 82**   | 0 / 6     | 0 / 7     | (aborted infra-side, p9 partial) |
| 09 |  92 / 92 | **83 / 92**   | 0 / 7     | (stopped at p8) | aborted |
| 10 |  99 / 99 | _in progress_ | 0 / 8     |           |  |
| 11 | 109 /109 | _pending_     | 0 / 9     |           |  |
| 12 | 116 /116 | _pending_     | 0 / 10    |           |  |

## Gemma-4 per-phase wall time

13 h 18 m of wall to land phases 1–9. Phase 10 in progress. Gemma is much slower
per phase than Sonnet (Sonnet baseline was ~30 min total for all 12 phases via
subagent) but it is *making real code* like Sonnet would.

| phase | total wall (min) | impl finish | sev finish | fix attempts | final passed/failed |
|---:|---:|---|---|---:|---:|
| 01 |  48.1 | done       | done       | 1 (no-op) | 11 / 0 ✓ |
| 02 | 171.0 | api_error  | api_error  | 1         | 12 / 12  |
| 03 | 114.3 | done       | step_cap   | 2 (37→39) | 39 / 0 ✓ |
| 04 |  72.7 | api_error  | done       | 1         | 47 / 0 ✓ |
| 05 |  53.8 | step_cap   | done       | 1         | 55 / 0 ✓ |
| 06 |  87.0 | api_error  | done       | 1         | 65 / 0 ✓ |
| 07 |  29.7 | done       | done       | 1         | 71 / 0 ✓ |
| 08 |  96.1 | step_cap   | step_cap   | 1         | 78 / 4   |
| 09 |  85.2 | api_error  | step_cap   | 1         | 83 / 9   |

The **per-phase fix-iteration loop earned its keep on phase 3**: the initial
selfeval ended with 37/2 (two failing tests); fix_01 brought it to 39/0; fix_02
confirmed no further progress and stopped. That's exactly the design intent —
let the model iterate while pass count strictly increases, then quit.

## Failure modes seen on Gemma (much less catastrophic than qwen3.6)

The "peg-native parser-500 from `<think>` exhausting `max_tokens`" failure that
defined Runs 6 and 7 **does not appear here at all.** Server uses
`Chat format: peg-gemma4`, which correctly separates `<think>` into a separate
`reasoning_content` field instead of inlining it. Confirmed: 0 occurrences of
"Failed to parse input" across the whole run.

What DID appear — at 5 events total across 9 phases:

1. **`Failed to parse tool call arguments as JSON`** — phase 2 implement step 17,
   phase 2 selfeval step 24, phase 4 implement step 27. The model emits a tool
   call with malformed JSON arguments. Recoverable: the harness records api_error
   and stops the loop, but the workdir state is preserved and subsequent stages
   (selfeval, fix) make progress.
2. **`request (~66K tokens) exceeds the available context size (65536)`** — phase 6
   implement step 72 (65,618 tokens), phase 9 implement step 63 (66,584 tokens).
   This is the same ctx-overflow we saw on the 16K-ctx probe last week, just at
   the 64K level. Driven by Gemma emitting verbose `reasoning_content` that
   accumulates across implement-loop turns.

Both are mild compared to qwen3.6's deterministic per-phase 500s. Gemma still
hits *some* phases (1, 7, 5) cleanly with no api_errors at all.

## Status one-liner

**Run 8 (B_gemma4) is mid-flight, phase 10/12 in progress. 9 phases committed,
83/92 cumulative tests passing.** Driver pid 47951, server pid 47613 (RSS 18.6 GB,
healthy). ETA for phases 10–12 at the observed average ~1.5h/phase = ~4–5 more
hours of wall time.

## All runs on the books (chronological in this session)

### Run 6 — Qwen3.6-35B-A3B Q? @ 64K (B_qwen36), 2026-05-22→23
- Setup: thinking on, max_tokens=4096, no iterating driver.
- Result: phase 1 only (11/11); phases 2-12 all `api_error` (peg-native 500s from
  `max_tokens` truncating the tool-call XML after `<think>` ate the budget).
  Phase 2 selfeval wrote partial parser.py before its own 500 → poisoned every
  later phase's seed → 0/0/0… cascade. **Effective 11/116.** 8 h 42 m wall.
- Writeup: `results/run_qwen36.md`.

### Run 7 — Qwen3.6-35B-A3B with thinking OFF (B_qwen36_iter), 2026-05-23
- Setup: same model, `enable_thinking=false` via `chat_template_kwargs`,
  max_tokens=8192, iterating fix loop.
- Result: zero parser-500s (the fix on that axis worked) but the model wrote
  ZERO files after phase 1, never called `done`, ran the IDENTICAL
  `find ... test_*` command 54/80 implement steps. Pattern: thinking-off breaks
  agent planning. **Effective 11/116.** Stopped by user at phase 8.
- Writeup: `results/run_qwen36_iter.md`.

### Run 8 — Gemma-4-26B-A4B Q4_K_M (B_gemma4), 2026-05-23→24 [IN PROGRESS]
- Setup: thinking on (Gemma's design — surfaces correctly as `reasoning_content`),
  max_tokens=8192, iterating fix loop, `peg-gemma4` parser.
- Result so far: phases 1–9 committed, 83/92 cumulative tests passing (~90%);
  six phases at exactly Sonnet's pass count. Phase 10 in progress.
- This doc.

### (Earlier runs, for reference)
- Run 5  Qwen2.5-Coder-32B Q4_K_M @ 32K (B_32bcoder) — aborted phase 9, peak 8 passes (phase 4), 0/116 effective. ~15 h.
- Run 5b Qwen2.5-Coder-32B @ 16K probe — 20% faster but ctx overflowed at phase 3.
- Run 3  Sonnet-4 via Claude Code subagent — **116/116, 53 min total wall.**
- Run 2  qwen3-coder-30b — 23/116 after litter-strip regrade.
- Run 1  Sonnet + qwen3-coder-30b phases 1–3 only.

## What this run resolves vs. what's still open

**Resolved by this run:**
- "Is the agent-loop benchmark possible on a 32 GB Mac with a local model?" — **Yes,
  on this model.** Gemma-4-26B-A4B at Q4_K_M fits RSS 18 GB, 64K ctx with q8_0 KV
  hybrid SSM model, 17–18 t/s gen, and produces work that matches Sonnet on most phases.
- "Is `peg-native` parser-500 model-specific or generic?" — Model-specific.
  `peg-gemma4` does not have the same fragility.
- "Does the per-phase fix-iteration loop earn its keep?" — Yes (phase 3: 37→39).
- "Does turning thinking off fix the parser-500?" — Yes BUT it destroys planning.
  Net result: same effective score as thinking-on. **Don't do this.**

**Still open / future work:**
- Why phase 2, 8, 9 fall short of Sonnet by 12, 4, 9 tests. Worth diffing the
  actual implementations once the run completes.
- Whether headless-via-SSH gives a different/better outcome (RAM headroom +
  bigger `max_tokens` or `-c 131072`) — held in reserve, see SESSION_STATE.md.
- Whether Q5_K_M would change anything material (better quality, ~21 GB RSS
  closer to the wired-limit headroom). Q5 partial was dropped from the parallel
  pull when HF reset the connection at 9.7 GB; resume from there is trivial if
  wanted.
