# Design changes for the next benchmark run

The first run finished phases 1–3 cleanly. Two problems showed up:

1. **The local model was ~30× slower per step than Sonnet.** Reasoning mode
   (`--reasoning-format deepseek`) emits long `<think>` blocks before every
   tool call. Combined with context growth from carry-forward files +
   accumulating tool transcripts, qwen took 4.4h on Phase 3 alone.
2. **The harness is strictly sequential per phase.** Each phase blocks on the
   slowest model. The fast model sits idle while the slow one grinds. If the
   slow side hits a wall, the run-all stalls there.

The first matters because we don't want to wait two days for one benchmark.
The second matters for the *design intent* of the benchmark — we want each
model to work at its own pace without being blocked by the other, and only
re-converge at cross-eval time.

## Changes for next run

### 1. Turn off reasoning mode for the local model

Edit `config/llmgateway.defaults.yaml` (or override in `llmgateway.yaml`) on
the `local` service entry:

```yaml
extra_args:
  # remove or comment these two lines:
  # - "--reasoning-format"
  # - "deepseek"
```

This should drop wall time per step by 5–10×.

Alternative: add a separate LiteLLM route `local-coding-fast` that hits the
same backend but is run without thinking turned on, and keep the original
`local-coding` for reasoning-mode comparisons.

### 2. Checkpoint each phase as a git commit per model

After each `(model, phase)` finishes implement + self-eval, commit the
workdir to `test/benchmark-tinylang`:

```
benchmark/ModelA/phase_03 → commit "benchmark A phase 3 — Sonnet"
benchmark/ModelB/phase_03 → commit "benchmark B phase 3 — local"
```

Two benefits:
- The two models do not block each other. Sonnet finishes phase 12 while
  qwen is still on phase 3. Each commits independently.
- Cross-eval reads from the committed snapshot, so it can run later in any
  order without the source moving under it.

Implementation outline for `harness.py`:

- After `run_phase_for_model(...)` returns, `git add benchmark/ModelX/phase_NN`
  and commit with a deterministic message.
- A new subcommand `cross-eval --phase N --reviewer X --target Y` reads the
  committed snapshot of `ModelY/phase_NN`. The current sandbox already maps
  the workdir, so no semantic change is needed — just call this at any time.
- `run-all` becomes two independent pipelines (one per model), each running
  all phases, with cross-eval invoked at the end (or after each phase if you
  want both perspectives mid-run).

### 3. Parallelize the two models

With per-model checkpoints, `run-all` can spawn two child processes:

```
python harness.py model-pipeline --model A &   # phases 1..12 for Sonnet
python harness.py model-pipeline --model B &   # phases 1..12 for local
wait
python harness.py cross-eval-all               # all phases, both directions
python harness.py final-eval
```

The persistent monitor watches both logs. Sonnet finishes in ~30–60 minutes;
local finishes whenever it finishes; cross-eval runs once both are done (or
once each phase is committed, if you want streaming reviews).

### 4. Higher step cap for the local model on self-eval

Phase 2 and Phase 3 both hit `STEP_CAP_SELFEVAL = 40` for qwen with real
failures still present. Two options:

- Raise the cap to 80 globally. Sonnet never approached 40 so this only
  matters for the local side.
- Make the cap model-specific: `STEP_CAP_SELFEVAL = {"A": 40, "B": 80}`.

### 5. Per-step time cap

If reasoning mode stays on for some routes, add a per-step `max_tokens`
budget tied to step number (e.g., decay max_tokens after the first 10 steps
to discourage long ramblings late in the loop). Optional.

### 6. Reset between models — fairer per-phase comparison

The current design seeds phase N from phase N-1 within the same model.
That's correct for *agent-style continuity* but means the slow model on
phase N inherits its own bugs from phase N-1 (e.g., qwen's missing `&&`
broke all later phases). A variant worth A/B testing: each phase seeds from
a known-good reference snapshot (Sonnet's, or a hand-written gold copy),
so each phase is graded *in isolation*. Decide which variant you want
before the rerun.

## What to keep

- The 12-phase tinylang spec is good. Don't regenerate.
- The 5-tool sandbox is good. Don't change.
- The cross-eval prompt and the score tool are good.
- The Sonnet results from this run are a solid baseline to compare future
  local-model runs against — keep them under
  `benchmark/results/baseline_sonnet_2026-05-18/` after committing.
