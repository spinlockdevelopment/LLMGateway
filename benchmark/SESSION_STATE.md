# Benchmark session state — handoff doc

Written 2026-05-18 at ~15:00 ET before clearing chat context.
**A live run is in progress in the background. Read this whole file before doing anything.**

## Overview

This is a 12-phase tinylang interpreter coding benchmark. Two coding models
under test, both going through the local LiteLLM proxy on `localhost:4000`:

- **Model A** = Sonnet 4 (`claude-sonnet` route → OpenRouter)
- **Model B** = local-coding qwen3.6-35b (`local-coding` route → llama-server on :8082)

The benchmark progresses through 12 incrementally-harder phases of building a
small dynamically-typed scripting language ("tinylang") in Python. Each phase
has a brief + a hidden acceptance test suite. Each model implements →
self-evaluates (tests revealed) → fixes → done. After each phase, both models
cross-evaluate the other's work (read-only). Opus grades at the end.

## What we did

### Run 1 (committed: `5d4c987 benchmark: scaffold + phases 1-3 results`)
Built the scaffold and ran phases 1-3 for both models.
- Sonnet 4: 39/39 acceptance tests, 11.4 minutes total, perfect.
- local-coding (`local-coding`, no extra config): 34/39, **6.6 hours**.
- Discovery: qwen was ~30× slower per step than Sonnet, because reasoning
  mode (`--reasoning-format deepseek` + `enable_thinking` defaulting to on)
  was emitting long `<think>` blocks before every tool call. Each phase's
  context grew, latency grew with it.
- Cross-eval finding: Sonnet's reviews catch real bugs (e.g. flagged missing
  multi-char punct in qwen's lexer). qwen's reviews are unstable — generous
  on phases 1–2, hallucinated missing functions on phase 3.
- Halted after Phase 3 cross-eval. Grades in `results/opus_grades.md`.

### Experiment 1 — reasoning A/B/C (committed: `962973e A/B/C reasoning experiment`)
Phase 1 only, local model, three reasoning configs side by side:
- `thinkon` (default = thinking on, max_tokens=4096): 711s, 10/11 tests.
- `thinkoff` (`enable_thinking=false`, max_tokens=4096): 338s **2.1× faster**, 8/11.
- `capped` (default, max_tokens=2048): **662s, 11/11** ← winner on both axes.
- The `--reasoning-format` llama-server flag is **cosmetic** — controls
  output channel, not whether the model thinks. Actual thinking is governed
  by chat_template_kwargs.enable_thinking.
- The LiteLLM `local-reason` route is misconfigured (points at :8084 with no
  server). To force thinking-off, the harness now passes
  `extra_body={"chat_template_kwargs":{"enable_thinking":false}}` against
  the working `local-coding` route. See `--extra-body-json` flag.

### Run 2 (in progress) — 12-phase local-only, max_tokens=4096
After capped (2048) **failed Phase 2 with tool-call truncation** — model
emitted `<tool_call><function=write_file>...` truncated mid-write; llama-server
rejected the malformed XML with `Failed to parse input`. Capped is unsafe for
file writes larger than ~2000 output tokens.

Restarted at **14:55:41 EDT 2026-05-18** with `max_tokens=4096` (thinkon
equivalent). Phase 1's existing 11/11 snapshot in `ModelB_capped/phase_01/`
is the starting point. Phases 2–12 will run with per-phase git commits.

## **CURRENT STATE — Run 2 COMPLETE**

Run 2 finished 19:12:25 EDT 2026-05-18 — total wall time 4h 17m for
phases 2–12. No background processes are still running. All 11 phases
were committed (`28a617d` through `e958298`).

**Read `results/run2_summary.md`** for the full per-phase table, the two
critical findings (pytest collection-litter + destructive regression of
`tinylang.evaluator.run` in Phase 4), and the four harness improvements to
ship before the next experiment.

### Next things to do, in order

1. Strip scratch litter (`debug_*.py simple_*.py minimal_*.py test_*.py at
   workdir root, NOT under tests/`) from each phase workdir and re-run
   `pytest tests/` for the true pass rates. The in-run numbers are mostly
   collection errors, not real failures.
2. Update `results/opus_grades.md` with Run 2 grades (additive — keep
   Run 1 grades for comparison).
3. Implement the four harness fixes in `run2_summary.md` before queueing
   the smaller-model experiment.
4. Decide on Sonnet phases 4–12 (yes/no) for cross-eval coverage.

## How to resume in a fresh chat

1. **Check if the run is still alive:**
   ```bash
   cd /Users/llmadmin/src/LLMGateway/benchmark
   ps -ef | grep -E "harness|run_capped" | grep -v grep
   tail -40 results/run_capped/RUNNER.log
   ls ModelB_capped/                       # which phases finished
   ```

2. **If it's still running, just monitor:**
   ```bash
   # in the same shell, watch progress
   tail -f results/run_capped/RUNNER.log
   ```

3. **If it died mid-phase**, the per-phase commits in
   `git log --oneline | grep B_capped` tell you the last clean phase.
   Restart from the next phase by editing `run_capped_2_to_12.sh`
   (`START_PHASE=` line) and re-launching with `nohup bash ... &`.

4. **When the run completes (Phase 12 done):**
   ```bash
   # Cross-eval each phase: Sonnet reviews qwen, qwen reviews Sonnet
   # Note: Sonnet only has phases 1-3 committed (ModelA/phase_01..03).
   # Cross-eval for phases 4-12 has no Model A counterpart unless we also
   # run Sonnet on those phases. Decide before invoking cross-eval.

   # If you want cross-eval against the Sonnet baseline (phases 1-3 only):
   for n in 1 2 3; do
       ./.venv/bin/python harness.py cross-eval --phase $n
   done

   # Final whole-project review:
   ./.venv/bin/python harness.py final-eval
   ```

5. **Opus grading**: read the workdirs and cross-eval JSON, update
   `results/opus_grades.md` with per-phase scores for the new run, and
   commit.

## Directory map

```
benchmark/
  README.md                         # how to use the harness
  NEXT_RUN.md                       # design notes for *future* reruns (per-model parallel pipelines)
  SESSION_STATE.md                  # this file — handoff for the current run
  harness.py                        # the agent harness; OpenAI client → litellm; 5 tools; CLI flags
  run_capped_2_to_12.sh             # the in-progress 12-phase runner
  exp_phase1_reasoning.sh           # the A/B/C reasoning experiment (already run)
  .gitignore                        # ignores .venv/, transcripts/ NOT ignored

  spec/
    overall_brief.md                # tinylang language spec — read first per phase
    phase_NN_<topic>.md             # 12 phase briefs
    tests/phase_NN/test_*.py        # acceptance tests, hidden during implement

  ModelA/phase_01..03/              # Sonnet snapshots from Run 1 (committed)
  ModelB/phase_01..03/              # qwen Run 1 snapshots (committed; 8-34 of 39 pass)
  ModelB_thinkon/phase_01/          # A/B/C experiment artifact (committed)
  ModelB_thinkoff/phase_01/
  ModelB_capped/phase_01..??/       # the IN-PROGRESS run; per-phase commits land here
  .venv/                            # python venv with openai + pytest (NOT committed)

  results/
    timings.csv                     # one row per (phase, model, stage)
    opus_grades.md                  # written after Run 1; needs update after Run 2 done
    self_eval/<label>/phase_NN.json # implement+self-eval results, per phase per model
    cross_eval/<reviewer>_on_<target>/phase_NN.json  # score-tool output
    cross_eval_final/<r>_on_<t>.json
    transcripts/*.json              # full message-by-message tool transcripts
    exp_phase1/                     # A/B/C experiment outputs (committed)
      RESULTS.md
      <variant>.harness.log
      <variant>.litellm.log         # docker logs of llm-gateway during the variant
    run_capped/                     # IN-PROGRESS run's per-phase logs
      RUNNER.log
      phase_NN.harness.log
      phase_NN.litellm.log
```

## Key files to read first

- `benchmark/results/opus_grades.md` — Run 1 grades (phases 1-3). Will need
  amending after Run 2.
- `benchmark/results/exp_phase1/RESULTS.md` — A/B/C experiment writeup.
- `benchmark/NEXT_RUN.md` — design changes for *future* runs beyond this one
  (per-model parallel pipelines, etc. — not implemented yet).

## Important findings to keep in mind

1. **Capped (max_tokens=2048) is unsafe** for tool calls that write large
   files. Qwen3.6-35b emits malformed `<tool_call><function=...>` XML when
   truncated mid-output, and llama-server's tool-call parser rejects it.
   Use 4096 minimum.

2. **`--reasoning-format` is cosmetic.** It controls how `<think>` blocks
   are surfaced in the response, not whether they're emitted. To actually
   disable thinking, use `chat_template_kwargs.enable_thinking=false`.

3. **The `local-reason` LiteLLM route is broken** — points at port 8084
   with no llama-server backing it. Either fix the route to point at :8082
   (same as `local-coding`) or pass `extra_body` per-request.

4. **Sonnet's cross-eval reviews are reliable; qwen's are not.** Phase 3,
   qwen scored Sonnet 30/40 by hallucinating missing functions in code that
   was working perfectly. Don't trust B-as-reviewer scores without a sanity
   check.

5. **qwen on M4 with 131K context, thinking on:** wall-time per tool call
   grew 13.6s → 22s → 414s across phases 1-2-3 in Run 1, as context grew.
   Same is likely to happen in Run 2 unless something changes.

6. **The branch is `test/benchmark-tinylang`**, local-only, not pushed.
   Run-2 commits are landing on this branch as they happen.

## Tasks not yet done

- Wait for Run 2 to finish (~hours).
- Decide whether to also run Sonnet on phases 4-12 for full cross-eval coverage.
- Cross-eval and final-eval after Run 2 completes.
- Update `results/opus_grades.md` with Run 2 grades, compare to Run 1.
- Optionally fix the `local-reason` route in LiteLLM config (separate concern).
- Optionally implement the per-model parallel pipeline design from `NEXT_RUN.md`.
