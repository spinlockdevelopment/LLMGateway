# tinylang model benchmark

A head-to-head reasoning benchmark: two coding models implement the same
12-phase tinylang interpreter, each in a sandboxed workdir, each self-evaluating
to fix failures, each cross-evaluating the other's work after every phase.

## Models under test

| Slot | Display name              | LiteLLM model ID  | Backed by                                  |
|------|---------------------------|-------------------|--------------------------------------------|
| A    | Sonnet 4                  | `claude-sonnet`   | Anthropic Claude Sonnet 4 (via OpenRouter) |
| B    | local-coding              | `local-coding`    | qwen3.6-35b on a local llama-server        |

Both go through `http://localhost:4000/v1` (LiteLLM proxy) using the same
OpenAI-compatible chat-completions API and the same five tools, so the only
moving part across models is the model itself.

## Phases

```
01  Lexer
02  Parser → AST
03  Evaluator (arithmetic, booleans, print)
04  Variables, assignment, block scope
05  Control flow (if / while / break / continue)
06  Functions (decls, calls, recursion)
07  Closures
08  Lists
09  Dicts + for-in
10  Error model (typed exceptions, stack traces)
11  Stdlib written in tinylang itself
12  CLI + REPL
```

Each phase brief lives at `spec/phase_NN_*.md`. The acceptance tests live at
`spec/tests/phase_NN/test_*.py`. **Tests are hidden during implement** — the
model must reason about the brief alone — and revealed only during self-eval.

## Per-phase flow

For each phase, for each model, in order:

1. **Implement.** Workdir is seeded from the prior phase's snapshot. The model
   sees the overall brief + the phase brief, and works via 5 tools
   (`read_file`, `write_file`, `edit_file`, `list_dir`, `run_bash`). It must
   call `done(summary)` to terminate. Step cap: 80 tool calls.
2. **Self-eval.** The acceptance tests for this phase are dropped into
   `tests/`. The model is told to run `pytest -q`, fix what it can, and re-run
   until passing or out of steps. Step cap: 40.
3. **Record.** Wall time, step count, token usage, and final pytest result
   land in `results/self_eval/{A,B}/phase_NN.json` and `results/timings.csv`.

Once both models finish a phase, **cross-eval** runs:

4. Model A reviews Model B's workdir, read-only (`read_file`, `list_dir`
   only). Score is submitted via a `score(accuracy, completeness, rationale)`
   tool call. Same for B reviewing A. **No fixes** — the two implementations
   are frozen for that phase.
5. Records land in `results/cross_eval/{A_on_B,B_on_A}/phase_NN.json` and
   `results/timings.csv`.

After all 12 phases finish, **final eval** runs once:

6. Each model reviews the other's full final-phase snapshot. Scored the same
   way. Records land in `results/cross_eval_final/{A_on_B,B_on_A}.json`.

Finally, **Opus grades** the whole thing manually by reading the snapshots and
both sets of cross-eval scores. The Opus grade lands in `results/opus_grades.md`.

## Usage

```bash
# from benchmark/
./.venv/bin/python harness.py models                  # smoke test
./.venv/bin/python harness.py phase --num 1 --model A # one phase, one model
./.venv/bin/python harness.py phase --num 1           # one phase, both models
./.venv/bin/python harness.py cross-eval --phase 1    # both directions
./.venv/bin/python harness.py final-eval              # final whole-repo review
./.venv/bin/python harness.py run-all                 # phases 1..12 + final
./.venv/bin/python harness.py run-all --start 5 --end 8   # subset
```

Environment overrides:

```
LITELLM_URL          default http://localhost:4000/v1
LITELLM_MASTER_KEY   default sk-gateway-master-change-me
```

## Results layout

```
benchmark/
  results/
    timings.csv                     # phase,model,stage,elapsed,steps,tokens,...
    self_eval/A/phase_NN.json       # one per phase per model
    self_eval/B/phase_NN.json
    cross_eval/A_on_B/phase_NN.json # one per direction per phase
    cross_eval/B_on_A/phase_NN.json
    cross_eval_final/A_on_B.json    # whole-project final
    cross_eval_final/B_on_A.json
    transcripts/                    # full message-by-message tool transcripts
    opus_grades.md                  # filled in by hand at the end
```

## Sandboxing

- All tool paths resolve relative to the model's per-phase workdir; absolute
  paths and `..` escapes are rejected.
- `run_bash` runs with `cwd=workdir` and a 60s timeout per command.
- Cross-eval runs in **read-only** mode: only `read_file`, `list_dir`, and the
  terminating `score` tool are available.

## Grading

Two axes, 0–100 each:

- **Accuracy** — how correct and bug-free is the code; would the acceptance
  tests pass.
- **Completeness** — how well does it cover the brief, including edges, error
  messages, and code organization (tests do not exhaustively cover every line
  of the brief).

Per phase, three scores: A's self-result (test pass count), B's self-result,
and each cross-eval score. Final grades by Opus reconcile these.

## Knobs

- `STEP_CAP_IMPLEMENT = 80`, `STEP_CAP_SELFEVAL = 40`, `STEP_CAP_CROSSEVAL = 40`
- `BASH_TIMEOUT = 60`
- `TEMPERATURE = 0.2`
- `MAX_TOKENS = 4096`

All in `harness.py` near the top.
