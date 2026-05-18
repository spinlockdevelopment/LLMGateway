# Run 2 — 12-phase local-only, max_tokens=4096 — COMPLETE

Started 14:55:41 EDT 2026-05-18 from Phase 1 capped snapshot (11/11 pass).
Finished 19:12:25 EDT. **Total wall time: 4h 17m** for phases 2–12.

Per-phase committed snapshots on `test/benchmark-tinylang`:
`28a617d..e958298` (one commit per phase, `B_capped phase NN — local capped`).

## Per-phase timing + reported test results

| Phase | Implement | Self-eval | pytest (reported) | Notes |
|---|---|---|---|---|
| 02 | 29 / 619s | 40 / 1373s (cap) | 14 pass, 10 fail | clean — actually ran tests |
| 03 | 60 / 1013s | 40 / 657s (cap) | 0 pass, 1 fail | collection error: scratch file `test_evaluator.py` has unmatched `)` |
| 04 | 46 / 1392s | 29 / 105s | 0 pass, 8 fail | **`run` removed from `tinylang.evaluator`** → all real tests fail to import |
| 05 | 23 / 512s | 16 / 47s | 0 pass, 2 fail | scratch + the regression |
| 06 | 67 / 1153s | 40 / 378s (cap) | 0 pass, 2 fail | same |
| 07 | 34 / 538s | 22 / 134s | 0 pass, 2 fail | same |
| 08 | 68 / 943s | 11 / 32s | 0 pass, 2 fail | model gave up on self-eval fast |
| 09 | 78 / 1837s | 40 / 539s (cap) | 0 pass, 2 fail | longest phase; ~30 min wall |
| 10 | 5 / 1387s **api_error** | 40 / 250s (cap) | 0 pass, 17 fail | tool-call truncation came back at 4096 too |
| 11 | 47 / 499s | 40 / 288s (cap) | 0 pass, 8 fail | scratch litter |
| 12 | 71 / 1269s | 40 / 427s (cap) | 0 pass, 2 fail | CLI/REPL implemented; tests un-runnable |

(Format: `steps / wall-seconds`.)

## Key signal

The pytest numbers are mostly noise from Phase 3 onward. Two issues compounded:

1. **Scratch litter at workdir root.** From Phase 3 onward the model wrote
   ad-hoc debug/test files (`debug_*.py`, `simple_test.py`, `test_evaluator.py`,
   etc.) into the workdir root rather than in `tests/`. One of them
   (`test_evaluator.py`) had a syntax error from the start. pytest's
   auto-discovery collects from the workdir root by default and aborts at the
   first syntax error, so the real acceptance tests in `tests/` never load.

2. **Destructive regression of prior-phase code.** In Phase 4 the model
   removed (or renamed) `tinylang.evaluator.run` — a Phase 3 deliverable that
   four prior-phase test files import. Every Phase-1-to-3 test fails with
   `ImportError: cannot import name 'run' from 'tinylang.evaluator'`. The
   `run` function did not return in any later phase.

3. **API errors recurred at max_tokens=4096.** Phase 10 hit the same
   malformed-`<tool_call>` truncation we saw on capped(2048) at Phase 2.
   With ~50K+ input tokens of carry-forward, even 4096 output isn't enough
   for some single-tool-call writes — or the qwen3 chat template is
   misbehaving under load.

The 14/24 score on Phase 2 (vs Run 1's 21/24 with a worse starting point) is
itself evidence for the context-degradation hypothesis in `NEXT_RUN.md`.

## What the committed code actually contains

Phase 12's workdir (`benchmark/ModelB_capped/phase_12/`) is the model's final
output. To grade it manually:

```bash
cd benchmark/ModelB_capped/phase_12
ls tinylang/                  # see what modules exist
# remove the scratch litter that breaks pytest:
rm -f test_*.py simple_*.py debug_*.py minimal_*.py detailed_*.py very_*.py
# now run the real tests:
../../.venv/bin/python -m pytest -q tests/ --tb=line
```

That tells us, file-by-file, whether the model's code passes the acceptance
tests once the litter is out of the way. **This is the right way to grade
Run 2** — the in-run pytest numbers underreport.

## Two follow-up experiments worth running

1. **Re-grade Run 2 after litter removal.** Strip scratch files from each
   phase's workdir, re-run `pytest tests/`, and tabulate "true" pass rates.
   May reveal the model did better than the in-run numbers suggest, OR
   confirm the regression of `evaluator.run` is real.

2. **Smaller model with same harness.** See `NEXT_RUN.md` for the
   context-degradation hypothesis. Candidates: Qwen2.5-Coder-14B/32B,
   DeepSeek-Coder-V2-Lite, Llama-3.1-8B, Phi-3.5-mini. Plot per-phase
   accuracy vs cumulative input-token count. If a smaller model holds
   accuracy past Phase 6, the diagnosis is confirmed.

## Harness improvements to ship before the next full run

- **Restrict pytest collection** to `tests/` only (e.g. `pytest tests/` in
  `run_final_pytest`, and tell the model in the self-eval prompt that only
  `tests/` is graded). One-line fix.
- **System-prompt nudge** against writing scratch files at workdir root.
  Already say "do NOT write planning files," but the model wrote them
  anyway — sharpen the wording or auto-delete on next implement turn.
- **Detect prior-test regression** during self-eval — keep a baseline of
  which tests passed at the prior phase, fail loudly if any of them break.
  Currently the model has no visibility that its Phase 4 edits broke
  Phase 1-3 tests.
- **Cleanup at phase boundary.** Before seeding phase N+1 from phase N,
  optionally `git clean -fd` the snapshot to drop scratch files.

## Files changed since SESSION_STATE.md was written

- 11 per-phase commits added (`28a617d` through `e958298`)
- This summary file
- `results/timings.csv` has 22 new rows (impl + self_eval per phase × 11
  phases, plus two abandoned api_error rows from the failed capped(2048)
  Phase 2 attempt)
- 11 new per-phase docker-logs files at `results/run_capped/phase_NN.litellm.log`
- Per-phase transcripts at `results/transcripts/phase_NN_B_*.json`

## Updated TODO (for the next session)

- [ ] Strip scratch litter from each phase workdir and re-run `pytest tests/`
      to get true per-phase pass rates.
- [ ] Read `tinylang/evaluator.py` at phase 12 to confirm whether `run` was
      restored or remained broken.
- [ ] Write Opus per-phase grades for Run 2 in `results/opus_grades.md`
      (additive — keep Run 1 grades for comparison).
- [ ] Decide whether to also run Sonnet on phases 4–12 for full cross-eval
      coverage, OR skip cross-eval and rely on Opus grading + the existing
      phase-1-3 Sonnet baseline.
- [ ] Implement the 4 harness fixes above before queueing the smaller-model
      experiment.
