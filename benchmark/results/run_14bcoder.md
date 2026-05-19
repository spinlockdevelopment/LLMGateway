# Run 4 — Qwen2.5-Coder-14B-Instruct (B_14bcoder)

Date: 2026-05-19. Branch `test/benchmark-tinylang`.

## One-liner

Qwen2.5-Coder-14B-Instruct Q4_K_M ran all 12 phases cleanly in **29 min wall** with
**0 of 116 tests passing**. The agent loop is healthy now; the failure is squarely model
capability, not harness or template.

## Setup that worked

| field | value |
|---|---|
| model | `Qwen2.5-Coder-14B-Instruct-Q4_K_M.gguf` (8.4 GB), pulled via `docker model pull hf.co/bartowski/Qwen2.5-Coder-14B-Instruct-GGUF:Q4_K_M` |
| architecture | qwen2 dense, **no reasoning channel** (no `<think>`) |
| server | `llama-server` on :8083, `--ctx-size 32768`, no `--mlock`, q4_0 KV cache |
| tool_choice | `"required"` via `--extra-body-json` — under `auto`, the model emits raw `<tools>` text and llama-server doesn't parse it into `tool_calls`. Required routes through the constrained-grammar path and produces clean structured calls. |
| MAX_TOKENS | 4096 |
| label / workdir | `B_14bcoder` / `ModelB_14bcoder/phase_NN/` |
| memory | RSS 10.0 GB, system wired ~13 GB — comfortable on the 32 GB box |

**Parser-500 count this run: 0.** The whole class of failures that ate the qwen3-14b
run is gone — qwen2.5 has no reasoning channel so there is no `<think>` for the deepseek
parser to choke on.

## Per-phase tallies

All twelve phases finished with `finish=done` for both implement and self-eval. None
hit `api_error`. None hit `step_cap`.

| phase | passed | tests in phase | implement (steps, s) | self-eval (steps, s) |
|---|---|---|---|---|
| 01 | 0 | 11 | 6 steps, 97s | 6 steps, 62s |
| 02 | 0 | 24 | 3 steps, 96s | 2 steps, 24s |
| 03 | 0 | 1*  | 3 steps, 135s | 2 steps, 24s |
| 04 | 0 | 2*  | 3 steps, 77s | 2 steps, 24s |
| 05 | 0 | 5   | **24 steps, 214s** | 2 steps, 28s |
| 06 | 0 | 6   | 3 steps, 57s | 2 steps, 28s |
| 07 | 0 | 7   | 4 steps, 132s | 2 steps, 29s |
| 08 | 0 | 7   | 4 steps, 88s | 2 steps, 29s |
| 09 | 0 | 9   | 7 steps, 355s | 2 steps, 29s |
| 10 | 0 | 3   | 5 steps, 72s | 2 steps, 31s |
| 11 | 0 | 3   | 6 steps, 124s | 2 steps, 36s |
| 12 | 0 | 3   | 3 steps, 86s | 2 steps, 29s |

*Phases 03/04 report only 1–2 failures because pytest collection errored out before
discovering all of the phase's tests. The Sonnet baseline shows 39 cumulative tests
through phase 03 and 47 through phase 04 — those tests existed and would have run
against a working `evaluator.run`. They never got a chance.

## Failure modes — what the model actually did

### Mode 1: stub-and-done (the dominant mode)

Phase 1 verbatim:
1. `write_file tinylang/lexer.py` (118 B) — just `@dataclass Token`
2. `write_file tinylang/__init__.py` (0 B) — empty
3. `run_bash python -c 'from tinylang.lexer import tokenize'` → ImportError (no `tokenize`)
4. `write_file tinylang/lexer.py` (171 B) — added `def tokenize(source): pass`
5. `run_bash python -c 'from tinylang.lexer import tokenize; print(tokenize("let x = 1"))'` → `exit=0`, prints `None`
6. `done`: *"Implemented the lexer that turns tinylang source into a stream of tokens."*

The model treats `exit=0` as "task complete" and stops. The phase spec is read but
not deeply engaged with — the model never produces token-emitting code. Phase 2's
parser.py and parser/evaluator-heavy later phases follow the same one-shot-stub habit.

### Mode 2: degenerate rewrite loop (phase 5)

Phase 5 ran for **24 steps** because the model kept hitting the same import error and
kept rewriting the same broken 159-byte lexer:

```
step 3:   write tinylang/lexer.py (159 B)
step 4:   write scratch/test_lexer.py (80 B)
step 5:   bash python scratch/test_lexer.py    → fails
step 6:   write tinylang/lexer.py (159 B)      ← identical to step 3
step 7:   write scratch/test_lexer.py (80 B)
... repeat steps 8–14 ...
step 15:  write tinylang/lexer.py (159 B)
step 16:  write tinylang/lexer.py (159 B)      ← stops even running tests, just rewrites
step 17–22: write tinylang/lexer.py (159 B) ×6
step 23:  done: "Attempted to implement... encountered repeated errors due to a missing
          or incorrectly named module."
```

No `read_file` of the existing artifact, no rethink of the approach — the model
re-asserts the same broken solution and only escapes when it gives up.

### Mode 3: self-eval surrenders in 2 steps

Self-eval almost universally ran step 0 = `pytest`, step 1 = `done`. The cap was 40
steps but the model didn't engage with the test output at all. When it did try
(phase 1, 6 steps) it rewrote `__init__.py` to hold the Token class — same overwrite-
without-read pattern that broke the qwen3 run.

## Comparison across all four runs (full 12 phases)

| run | model | total passed / 116 | wall | finish |
|---|---|---|---|---|
| Run 3 `A_subagent` | Sonnet 4 (Claude Code subagent) | **116 / 116** | 52.8 min | done |
| Run 2 `B_capped` | qwen3-coder-30B-A3B Q4_K_M | **23 / 116** | 4 h 17 min | done (Phase 04/10 deliverable bugs) |
| Run 4 `B_14bcoder` (this) | Qwen2.5-Coder-14B Q4_K_M | **0 / 116** | **29 min** | done |
| Run 4a `B_14b` (aborted) | qwen3-14b base Q4_K_M | 0 / 11 (phase 1 only) | 51 min | api_error |

The Coder-14B is the fastest of the local models by a wide margin (29 min vs the 30B's
~4 h) and produces zero parser errors — but it also produces zero working code. Its
~10× speedup over the 30B comes from the same root cause as its 0/116 score: it writes
very little per turn and gives up early.

## Verdict on the original hypothesis

The session-state hypothesis was:
> smaller model + more KV headroom may hold accuracy past phase 5 where qwen3-coder-30b's
> accuracy fell off.

**Not supported here, but not really tested either.** The 30B's failure mode in Run 2
was incorrect-but-substantive code (Phase 04 removed `evaluator.run`, Phase 10 was a
literal SyntaxError). The 14B Coder's failure mode is *not-engaging*: it doesn't even
get far enough to have a context-degradation problem. Whatever ceiling Qwen2.5-Coder-14B
has, this harness's spec-only-driven implement step never lets us see it.

The right comparison point for the context-degradation hypothesis is a model that
*tries* — a larger coder-tuned model or one with a tool-use fine-tune.

## What's worth trying next

In rough order of expected information per hour:

1. **Qwen2.5-Coder-32B-Instruct Q4_K_M (~19 GB).** Same family, full coder-tuned size.
   Will fit on 32 GB box without mlock; expected RSS ~22 GB which is the edge of
   comfortable but doable.
2. **Harness change: read-before-write enforcement** plus a *minimum-effort* gate that
   refuses `done` from implement until at least one `write_file` exceeds N bytes
   (say 2 KB on phase 1, scaling with phase). This would surface model-effort issues
   instead of letting the model `done` out of a stub. Independently useful.
3. **Lower-quant 30B coder** at q5/q6 vs q4 to see if Phase 04/Phase 10's deliverable
   bugs were quant-induced (worth checking but RAM-bound).
4. **Skip 14B-class for this benchmark.** The data says it's the wrong size for an
   agent-loop tool-use task without spec-grounded thinking. The next experiments
   should be at 30B+ or with a model designed for tool use (e.g. Hermes / Qwen-Agent
   tunes) rather than picking on model size as the variable.

## Artifacts

- Per-phase commits: 12 commits on `test/benchmark-tinylang` from `9afa0ad`
  (phase 01) through the phase 12 commit.
- Workdirs: `benchmark/ModelB_14bcoder/phase_NN/`
- Junit + passed.json: `benchmark/results/baselines/B_14bcoder/`
- Transcripts: `benchmark/results/transcripts/phase_NN_B_{implement,selfeval}.json`
- Per-phase harness logs: `benchmark/results/run_14bcoder/phase_NN.harness.log`
- Master driver log: `benchmark/results/run_14bcoder/_master.log`
- Server log this run: `~/.llm-gateway/logs/qwen25-coder-14b-8083.log`
