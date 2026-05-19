# Sonnet baseline — subagent-driven 12-phase run

**Run date:** 2026-05-19. Model: Claude Sonnet (Claude Code subagent harness, max-plan billed — not LiteLLM/OpenRouter API). Branch: `test/benchmark-tinylang`. Workdirs: `benchmark/ModelA_subagent/phase_NN/`. Per-phase commits `1f1bbc6..a963209`.

## Why a fresh run

The Run-1 Sonnet pass only covered phases 1–3. Run 2 was qwen-only. To put qwen Run 2 (avg accuracy 32, avg completeness 51, two catastrophic deliverable failures) into context, we needed a Sonnet baseline across all 12 phases under the *new* harness (pytest scoped to `tests/`, anti-scratch system prompts, regression baseline carry-forward, scratch sweep at phase boundary). That baseline is what this document tabulates.

## Protocol

Two sequential subagent invocations per phase, mirroring `harness.py`:

1. **implement** — workdir seeded from prior phase, no test files visible. Subagent gets the IMPL_SYSTEM prompt + overall + phase brief, returns when done.
2. **drop-tests** — copy `spec/tests/phase_NN/*.py` into `workdir/tests/`. Prior-phase tests remain (cumulative regression set).
3. **self-eval** — subagent runs `pytest tests/`, fixes failures, re-runs until passing or no progress. Prior-phase passing-test baseline embedded in the prompt.
4. **grade** — final `pytest -q tests/ --junitxml=...`, save passed-id list as next phase's baseline.
5. **commit** — one commit per phase.

Token counts come from the Claude Code subagent harness `<usage>` block (rough — counts the subagent's *own* context, not the user-facing turn). Wall-times include subagent queue + setup; small absolute differences shouldn't be over-interpreted.

## Per-phase results

| Phase | Tests | % | Implement wall | Impl steps | Self-eval wall | SE steps | Cum. tokens in | Cum. tokens out | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 01 lexer       | **11/11**   | 100% | 171.7s | 13 | 16.7s   | 1  | 21.8k | 4.5k | one-shot |
| 02 parser      | **24/24**   | 100% | 159.4s | 9  | 10.0s   | 1  | 28.6k | 5.0k | one-shot |
| 03 evaluator   | **39/39**   | 100% | 152.7s | 18 | 9.1s    | 1  | 30.8k | 5.0k | one-shot |
| 04 scope       | **47/47**   | 100% | 142.8s | 16 | 9.7s    | 1  | 30.2k | 5.0k | one-shot (qwen Run 2 was 0/47 here) |
| 05 control     | **55/55**   | 100% | 121.4s | 14 | 232.4s* | 1  | 28.3k | 5.0k | one-shot (*SE wall inflated by harness idle, only 1 tool call) |
| 06 functions   | **65/65**   | 100% | 202.6s | 27 | 9.1s    | 1  | 47.5k | 6.5k | one-shot |
| 07 closures    | **71/71**   | 100% | 141.5s | 16 | 236.1s* | 6  | 35.8k | 1.8k | recognized closures already worked from phase 6 |
| 08 lists       | **82/82**   | 100% | 168.8s | 24 | 21.2s   | 3  | 42.2k | 2.5k | one-shot |
| 09 dicts       | **92/92**   | 100% | 223.9s | 34 | 14.0s   | 2  | 53.7k | 2.5k | one-shot |
| 10 errors      | **99/99**   | 100% | 511.3s | 61 | 14.9s   | 2  | 88.0k | 6.5k | biggest phase by steps; one-shot (qwen Run 2 was 0/99 here) |
| 11 stdlib      | **109/109** | 100% | 143.3s | 16 | 222.2s  | 18 | 39.3k | 2.0k | self-eval caught + fixed a real regression: stdlib `sum` was binding into user globals and blocking `let sum = 0`; loader moved into a parent scope of user globals |
| 12 CLI/REPL    | **116/116** | 100% | 215.9s | 30 | 16.0s   | 3  | 57.6k | 2.0k | one-shot |

## Totals

| | Sonnet subagent (this run) | qwen3-coder-30b Run 2 | Sonnet Run-1 API (phases 1–3 only) |
|---|---|---|---|
| Phases attempted | 12 | 12 | 3 |
| Phases at 100% | **12** | 1 (phase 01 only) | 3 |
| Final cumulative tests passing | **116/116** | 23/116 | 39/39 |
| Avg accuracy (Opus) | **~100** (deferred — all phases pass) | 32 | 97 |
| Total wall time | **52.8 min** | 4h 17m | 11.4 min |
| Implement wall | 39.3 min (2355s) | ~3h 50m | 8 min |
| Self-eval wall | 13.5 min (811s) | ~27m | 3.5 min |
| Implement tool calls | 278 | ~580 | 106 |
| Self-eval tool calls | 40 | ~358 | 58 |
| Total input tokens (proxy) | ~688k | ~9M | ~1.86M |
| Total output tokens | ~56k | ~70k | ~40k |

(qwen Run 2 figures are pulled from `results/timings.csv` rows where `model="B"` and dates align; Sonnet Run-1 figures are from rows `model="A"`.)

## Observations

1. **Sonnet baseline is the ceiling on this benchmark — 116/116 across all 12 phases, one-shot for 11 of them.** The one phase where self-eval caught a real issue (Phase 11) was a subtle stdlib-loader scope collision, exactly the kind of thing the new regression-baseline self-eval prompt is designed to surface. The model fixed it in a single iteration.

2. **Token count proxy.** The subagent harness only reports `total_tokens` per stage, not separate input/output. The numbers in the "tokens in" column are the subagent's per-invocation `total_tokens` minus an estimate of output; they are roughly 8–10× lower than the Run-1 OpenRouter numbers because the subagent harness doesn't re-send tool transcripts on every step the way the OpenAI chat-loop does. So per-token cost on a max-plan subscription should compare extremely favorably to the OpenRouter cost — but the absolute numbers in this column are not a 1-to-1 substitute for OpenAI-API `prompt_tokens` and shouldn't be benchmarked against them directly.

3. **Implement wall ≫ self-eval wall.** Implement totals 39 minutes, self-eval 14 — about a 3× ratio, identical to Run-1 Sonnet (8 min impl vs 3.5 min self-eval over phases 1–3). The new harness's anti-scratch + regression-baseline prompts didn't measurably slow the implement stage.

4. **Two self-eval phases (05, 07) show inflated wall time (~230s) with only 1–6 tool calls each.** These are the Claude Code subagent runtime including queue/setup overhead, not actual model work. The token count for those phases (~12k–17k) confirms minimal work was done. Treat these as outliers when interpreting wall-time-per-step.

5. **Phase 10 was the steepest phase for Sonnet too** — 511s implement, 61 tool calls. It restructures the entire error model (lexer/parser/evaluator/builtins all touch the new `errors.py`) and stamps every position-tracking AST node. Sonnet finished it cleanly; qwen Run 2 wrote a literal Python `SyntaxError` into `errors.py` and got 0/99 here.

## Comparison to qwen3-coder-30b Run 2

Phases where qwen Run 2 scored 0 (P04 catastrophic regression; P10 SyntaxError) Sonnet handled in one shot. Phases where qwen Run 2 was partial (P02 58%, P03 38%, P05–11 17–33%) Sonnet was 100%. **There is no phase in this run where Sonnet was not at ceiling.**

This is the head-to-head baseline. Any future local-model rerun (qwen3-14b context-degradation experiment, smaller-context candidates) is compared to this 116/116 column.

## How to reproduce

`benchmark/bench_subagent_helper.py` is the bookkeeping wrapper. From `benchmark/`:

```bash
.venv/bin/python bench_subagent_helper.py seed <N>           # copy phase N-1 → N, sweep scratch
# (parent-context Claude Code subagent: implement)
.venv/bin/python bench_subagent_helper.py drop-tests <N>     # copy spec/tests/phase_NN → tests/
# (parent-context Claude Code subagent: self-eval)
.venv/bin/python bench_subagent_helper.py grade <N>          # pytest --junitxml + save passed_ids
.venv/bin/python bench_subagent_helper.py log <N> <stage> ...
.venv/bin/python bench_subagent_helper.py commit <N> --passed P --total T
```

The two subagent invocations themselves run from the orchestrating chat conversation, one Agent tool call per stage. Per-phase commits `1f1bbc6` (phase 01) through `a963209` (phase 12) on branch `test/benchmark-tinylang`.

## Artifacts

- `ModelA_subagent/phase_NN/` — per-phase workdir snapshots, one commit each.
- `results/baselines/A_subagent/phase_NN_passed.json` — junit-derived passing test ids.
- `results/baselines/A_subagent/phase_NN_junit.xml` — pytest output XML.
- `results/timings.csv` — 24 new rows (12 implement + 12 self_eval) under `model="A_subagent"`.
