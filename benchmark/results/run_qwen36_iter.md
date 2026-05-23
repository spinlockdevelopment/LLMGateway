# Run 7 — Qwen3.6-35B-A3B @ 64K, thinking OFF, iterated (B_qwen36_iter) — STOPPED at phase 8

Date: 2026-05-23. Branch `test/benchmark-tinylang`. Stopped by user mid-phase-8.
Phases 1–8 committed (`c6497eb..f5cf4ea`).

## Why this run

Run 6 (B_qwen36) failed every phase 2–12 with `peg-native` parser-500s caused by
`max_tokens=4096` truncating tool-call XML after the thinking budget was spent. This
re-run applied the pitfall #2 escape hatch — `chat_template_kwargs.enable_thinking=false`
in `--extra-body-json` — plus `max_tokens=8192`, fresh `ModelB_qwen36_iter/` root, and
a per-phase fix-iteration loop in a new driver (`run_qwen36_iter_1_to_12.sh`) that
re-runs selfeval-style on existing workdirs while pytest pass count strictly increases.

## Setup

- Server flags: identical to Run 6 (`-c 65536 -fa on -ctk q8_0 -ctv q8_0 -ngl 999 --jinja`).
- Driver: `run_qwen36_iter_1_to_12.sh`, label `B_qwen36_iter`, suffix `_qwen36_iter`,
  MAX_FIX=4, `max_tokens=8192`.
- Extra body: `{"tool_choice":"required","chat_template_kwargs":{"enable_thinking":false}}`.
- Harness change: new `fix` subcommand operating on existing workdirs (no re-implement,
  no test-redrop); records `fix_KK` timing rows and updates baseline + self_eval JSON.

## Result — STOPPED

| phase | impl finish | impl s | selfeval | fix_01 | passed/failed |
|---|---|---|---|---|---|
| 01 | step_cap (80) | 616.9 | done (12) | done (14) | **11 / 0** ✓ |
| 02 | step_cap (80) | 309.2 | step_cap (40) | step_cap (40) | 0 / 1 |
| 03 | step_cap (80) | 344.1 | step_cap (40) | step_cap (40) | 0 / 2 |
| 04 | step_cap (80) | 1024.4 | step_cap (40) | step_cap (40) | 0 / 3 |
| 05 | step_cap (80) | 325.1 | step_cap (40) | step_cap (40) | 0 / 4 |
| 06 | step_cap (80) | 291.0 | step_cap (40) | step_cap (40) | 0 / 5 |
| 07 | step_cap (80) | 322.7 | step_cap (40) | step_cap (40) | 0 / 6 |
| 08 | step_cap (80) | 477.6 | (killed) | — | — |

Wall time to stop: ~6900 s (~115 min). User killed at phase 8 implement.

**Effective: 11/116** — same as Run 6, achieved differently.

The `failed` column climbing 1, 2, 3, 4, 5, 6 isn't 24 tests failing in different ways —
it's pytest collection errors compounding. `drop_tests_for_phase` is additive (tests/
accumulates a file per phase), so each phase adds one new test module whose imports
break because the implementation never gets written.

## Root cause — `enable_thinking=false` broke the agent's planning

No more parser-500s — zero `api_error` finishes across the whole run. The fix on
that axis worked. But every implement loop hit `step_cap` (80 steps) without ever
calling `write_file` or `done`. Concrete numbers across all 22 implement/selfeval/fix
loops:

```
phase   stage      write_file  run_bash  read_file  list_dir  done  repeat-loop?
  1   implement       2         77         0          1        0      YES
  1   selfeval        0          4         4          3        1       -
  1   fix_01          0         10         2          1        1       -
  2   implement       0         72         5          3        0      YES
  2   selfeval        0         31         6          3        0      YES
  ...
  8   implement       0         74         3          3        0      YES
  8   selfeval        0         20        12          3        0       -
```

**`write_file` count after phase 1: zero, every phase, every stage.** The model
never edits a file after phase 1.

**`done` count: 1 in phase 1 selfeval, 1 in phase 1 fix_01, 0 everywhere else.** It
almost never signals completion.

**`repeat-loop?` flag** (3+ consecutive identical bash commands): **YES in 13 of 22
entries.** The most blatant case — phase 2 implement ran the IDENTICAL command
`find . -name "test_*" -type f 2>/dev/null | head -30` **54 times out of 80 steps**,
despite IMPL_SYSTEM explicitly stating "You do not have access to the acceptance tests
during implementation — you must reason about correctness from the brief alone."

Without `<think>`, the model can't internalize the prompt, can't form a plan, and
gets stuck looping on empty-result probes. The fix-iteration loop didn't rescue it
because it inherits the same model behavior — `fix_01` rows show the same churn
pattern.

Phase 1 still worked because phase 1 starts from an empty workdir and the brief
("implement a basic lexer") can be one-shot — no read-then-decide planning step needed.
From phase 2 onward, the model must read existing code, decide what to extend, then
write. That decide-step is what `<think>` was doing.

## What this means

We now have the two failure modes bracketing the answer:

| run | thinking | max_tokens | parser-500 | model can plan |
|---|---|---|---|---|
| B_qwen36 | on | 4096 | yes — truncates tool calls | yes |
| B_qwen36_iter | off | 8192 | no | **no** — degenerate loops |

The model needs `<think>` for agent-loop work. The parser-500 must be addressed by
giving thinking *room*, not by suppressing it.

## Next attempt (B_qwen36_hl) — thinking ON + bigger budget + headless SSH

Plan (now the leading entry in SESSION_STATE.md):

1. Thinking ON. EXTRA_BODY back to `{"tool_choice":"required"}` only.
2. `--max-tokens 16384` (~57K bytes output budget). Run B_qwen36 truncated at ~14K
   bytes → 4× headroom should clear it without needing chat-template changes.
3. `-c 131072`. Hybrid SSM model has the headroom (see [[qwen36-a3b-256k-headroom]])
   and the ctx is cheap memory-wise.
4. **Headless via SSH, GUI on, no user logged in** — see SESSION_STATE.md
   "Headless SSH fallback" section. Critical because 16K-token responses take much
   longer to generate (~16 t/s × 16K = up to ~17 min per step worst case) and we
   need the wired-RAM headroom (~6 GiB the Docker VM + GUI consume).
5. Reuse the iterating driver shape; same `fix` subcommand; fresh root
   `ModelB_qwen36_hl/`.

## State on disk at stop

- Per-phase commits `c6497eb..f5cf4ea` (label `B_qwen36_iter`, phases 1–8).
- Driver log: `/tmp/run_qwen36_iter_driver.log`.
- Per-phase logs: `benchmark/results/run_qwen36_iter/phase_*.harness.log`,
  `..._fix_KK.log`.
- Iterations table: `benchmark/results/run_qwen36_iter/iterations.tsv`.
- Transcripts: `benchmark/results/transcripts/phase_NN_B_implement.json`,
  `..._selfeval.json`, `..._fix_01.json` for phases 1–8.
- Server pid 19406 still up at stop (port 8083); should be killed before the next
  attempt boots a fresh server with new flags.
