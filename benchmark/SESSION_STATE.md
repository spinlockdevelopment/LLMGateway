# Benchmark session state — handoff doc

Last updated 2026-05-19 evening. Branch `test/benchmark-tinylang`, working tree clean.

## Status one-liner

Sonnet baseline (12/12 phases @ 100% via subagent) is complete and committed. Next session: test **qwen3-14b** as a smaller-model context-degradation candidate, BEFORE doing any system-level memory restructuring.

## Three runs on the books

### Run 1 — phases 1–3, both models, OpenAI-SDK harness (committed `5d4c987`)
- Sonnet 4 via OpenRouter: 39/39, 11.4 min
- qwen3-coder-30b local: 34/39, 6.6 h (reasoning-mode tax)
- Cross-eval done. Halted after Phase 3.

### Run 2 — phases 1–12 local-only, max_tokens=4096 (committed `28a617d..e958298`)
- qwen3-coder-30b only, 4 h 17 m wall. All 12 phases committed.
- Regraded after litter strip: 116-test suite ended at **23/116 passing**, avg accuracy 32, avg completeness 51.
- Two catastrophic deliverable failures: Phase 04 (removed `evaluator.run`), Phase 10 (literal SyntaxError in `errors.py`).
- See `results/run2_summary.md` and `results/run2_regrade.md`.

### Run 3 — Sonnet baseline via Claude Code subagent, phases 1–12 (committed `82f00b6..4a05751`)
- All 12 phases @ **100% / 116-of-116 tests**, 52.8 min total wall.
- 11 of 12 phases one-shot at implement. Phase 11 self-eval caught + fixed a real stdlib-loader scope bug.
- Tokens reported by subagent harness: ~744k total across 24 invocations (input ~688k / output ~56k approx).
- Estimated API cost equivalent: ~$1.50–$2.90 (paid via max-plan subscription instead).
- See `results/baseline_sonnet_subagent.md`.

## Harness improvements that have shipped

In `harness.py`:
- `pytest -q tests/` is the only thing graded (was `pytest -q` whole tree).
- `IMPL_SYSTEM` and `SELFEVAL_SYSTEM` ban scratch files at workdir root.
- `prepare_phase_workdir` sweeps `debug_*.py simple_*.py minimal_*.py detailed_*.py very_*.py final_*.py test_*.py *.tl *.py.backup` (preserving `tinylang_cli.py`, `stdlib.tl`).
- After every self-eval, the harness writes a junit XML and persists the list of passing test ids at `results/baselines/<label>/phase_NN_passed.json`.
- SELFEVAL prompt for phase>1 embeds the prior-phase passing-test list with regression priority.
- Console prints `⚠ regressed N prior-phase tests: …` after each phase whose passing set shrank.

In `bench_subagent_helper.py` (new — bookkeeping for Claude Code subagent runs):
- `seed <N>`, `drop-tests <N>`, `grade <N>` (writes junit + passed_ids), `log <N> <stage>`, `commit <N>`, `show-passed <N>`.
- Used to drive the Sonnet baseline run. The two subagent invocations per phase happen from the parent conversation; this script handles the deterministic glue.

## The kernel panic post-mortem (2026-05-18 23:31 EDT)

While prepping a qwen3-14b context-size sweep last session, the M4 box panicked with
`watchdog timeout: no checkins from watchdogd in 94 seconds`. Root cause was wired-memory
exhaustion: `memoryStatus.wired = 2,060,406 pages × 16 KiB ≈ 31.4 GiB` on a 32 GiB
machine, with free pages at 14 MiB. `--mlock` plus an oversized `--ctx-size` on llama-server
will wire everything; combined with the launchd `KeepAlive=true` policy on
`com.local.llm-gateway`, a respawned 30B running alongside a new 14B is enough to push wired
past system memory. Kernel had no pageable memory left, watchdogd starved, system panicked.

System recovered cleanly. 30B is currently running via launchd auto-respawn (PID was 1904
at 8:55 AM today, RSS ~19.8 GiB). No qwen3-14b experimental artifacts were persisted before
the crash.

## Plan for the next session — DO THIS BEFORE FREEING SYSTEM RESOURCES

Test the qwen3-14b candidate FIRST as a context-degradation experiment. The system-resource
restructuring is deferred until after we have the 14B data point.

### Safer relaunch checklist for the qwen3-14b sweep

Before launching any side llama-server:

1. `launchctl unload ~/Library/LaunchAgents/com.local.llm-gateway.plist` to stop the
   30B respawning. (Just stopping the process is not enough — see [[project_plist_regen]].)
2. `pgrep llama-server` returns nothing before continuing.
3. Drop `--mlock` for the sweep. The point is to discover what ctx fits; without mlock,
   the OS can page out and you get poor-throughput-but-alive instead of a kernel panic.
4. Cap total expected wired memory at ~24 GiB to leave OS headroom (~8 GiB).
5. Use `--ctx-size 131072` first; only raise to 262144 if RSS after model load + KV
   allocation is well under 24 GiB. Skip 524288 unless RSS at 262144 is < 15 GiB.

### Qwen3-14B GGUF location

`/Users/llmadmin/.docker/models/blobs/sha256/915913e22399475dbe6c968ac014d9f1fbe08975e489279aede9d5c7b2c98eb6`
(8.38 GB, already on disk from previous DMR pull).

### Suggested LiteLLM wiring

Either bypass LiteLLM entirely (point harness directly at `http://localhost:8083/v1` via
`LITELLM_URL` env) or add a new route `local-coding-14b` pointing at port 8083, leaving
`local-coding` (the 30B) on 8082 if you want to A/B them. The current LiteLLM yaml at
`config/llmgateway.defaults.yaml` plus the DB-stored routes need `/v1/model/info` to be
queried to see the live state — see [[reference_litellm_local]].

### Run protocol

Drive the 14B run with the existing `harness.py` (it already has all the new prompts and
the regression-baseline plumbing). Use `--workdir-suffix _14b --label B_14b` so workdirs
land under `ModelB_14b/phase_NN/` and timings get tagged `B_14b`. Compare to the
`A_subagent` 116/116 baseline and the Run 2 `B_capped` 23/116 ceiling.

### Hypothesis to test

From `NEXT_RUN.md`: smaller model + more KV headroom may hold accuracy past phase 5 where
qwen3-coder-30b's accuracy fell off. If the 14B at 131k ctx beats the 30B at 131k ctx on
phases 5–12, the diagnosis is context degradation (not parameter-count limit) and we
should explore even smaller models or aggressive context-trimming strategies.

## What's NOT next (deferred)

- **System resource restructuring** (the "we'll restructure to free up memory" plan).
  Postponed until after the 14B data point.
- Cross-eval against Sonnet for phases 4–12. The `A_subagent` snapshots are committed,
  so cross-eval can run any time; not blocking anything.
- Final-eval / whole-project Opus grading for the Sonnet baseline. The result is
  obvious (perfect), so grading is low-priority.
- `local-reason`, `local-fast` LiteLLM routes — still misconfigured per the May 18
  notes. Independent concern.

## How to resume in a fresh chat

```bash
cd /Users/llmadmin/src/LLMGateway/benchmark
git log --oneline | head -20            # confirm last commit is 4a05751
ls ModelA_subagent/                     # should show phase_01..12
cat results/baseline_sonnet_subagent.md # the Sonnet baseline writeup
.venv/bin/python bench_subagent_helper.py show-passed 12 --max 5  # spot-check baseline
```

Then read the "Plan for the next session" section above and start with the 14B safer
relaunch checklist.

## Directory map (updated)

```
benchmark/
  README.md
  NEXT_RUN.md                       # design notes for future reruns
  SESSION_STATE.md                  # this file
  harness.py                        # OpenAI-SDK harness for the API-side runs
  bench_subagent_helper.py          # NEW — bookkeeping for Claude Code subagent runs
  run_capped_2_to_12.sh             # Run 2 driver
  exp_phase1_reasoning.sh

  spec/                             # 12-phase briefs + hidden acceptance tests

  ModelA/phase_01..03/              # Run 1 Sonnet (committed)
  ModelB/phase_01..03/              # Run 1 qwen (committed)
  ModelB_thinkon/phase_01/          # A/B/C reasoning experiment
  ModelB_thinkoff/phase_01/
  ModelB_capped/phase_01..12/       # Run 2 qwen complete (committed)
  ModelA_subagent/phase_01..12/     # NEW — Run 3 Sonnet baseline (116/116 committed)

  results/
    timings.csv                     # rows per (phase, model, stage); A_subagent rows latest
    opus_grades.md                  # Run 1 grades + Run 2 grades
    run2_summary.md
    run2_regrade.md
    baseline_sonnet_subagent.md     # NEW — Run 3 writeup
    self_eval/<label>/phase_NN.json
    cross_eval/<reviewer>_on_<target>/phase_NN.json
    baselines/<label>/phase_NN_{junit.xml,passed.json}   # used by SELFEVAL prompt
    transcripts/*.json
    exp_phase1/                     # A/B/C experiment outputs
    run_capped/                     # Run 2 per-phase logs
```

## Important findings to keep in mind

1. `--mlock` + large `--ctx-size` on a 32 GiB machine is panic-prone. Last session burned
   one. Drop `--mlock` for any ctx-sweep work. See the post-mortem above.

2. `com.local.llm-gateway` has `KeepAlive=true` — stopping a llama-server process is not
   enough; the plist must be unloaded or `gw stop llama-server` used. Plain `kill` will
   respawn within seconds.

3. The Claude Code subagent harness is a viable path for Sonnet baselines without burning
   API credits. The `bench_subagent_helper.py` glue is reusable for any future
   subagent-driven runs.

4. The Run 2 regrade exposed that qwen's failure mode is NOT just litter — Phase 4 and
   Phase 10 were real deliverable bugs (removed function, literal SyntaxError). The new
   harness's regression-baseline self-eval prompt is specifically designed to surface
   these but qwen Run 2 predates that fix. Re-running qwen3-coder-30b under the new
   harness is a separate experiment from the 14B test, and worth doing eventually.

5. The branch is `test/benchmark-tinylang`, local-only, never pushed. Last commit on it
   as of this writeup: `4a05751`.
