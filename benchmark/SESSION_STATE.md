# Benchmark session state — handoff doc

Last updated 2026-05-21. Branch `test/benchmark-tinylang` — **PARKED, will NOT be merged.**
Working tree clean (everything below is committed on this branch for the record).

## Status one-liner — branch parked

This branch holds 5 benchmark runs (see "Runs on the books"). The local-model story is now
well characterized and there's a clear blocker: **running a 32B locally for the agent loop
on this 32 GB Mac is bottlenecked by the macOS GUI/Docker memory overhead, not by the
model.** Rather than keep fighting it on this branch, the decision (2026-05-21) is to
**leave this branch unmerged**, build proper headless infrastructure on a fresh branch off
`main`, and return here to re-run the benchmarks in headless mode.

## Forward plan (next work — NOT on this branch)

1. `git checkout main`, then **`git switch -c feat/<name>`** (a lightweight headless
   service shim).
2. Build a **lightweight service shim to run llama.cpp / whisper instances headless** —
   spin up/own `llama-server` (and whisper) processes without Docker and without a GUI
   session, so wired memory isn't eaten by WindowServer + Docker VM. Get that working
   correctly and tested on its own.
3. **Come back to this `test/benchmark-tinylang` branch** and re-run the benchmark suite
   in **headless mode** via the new shim. The headless boot is expected to free the
   several GiB of wired RAM that forced memory compression at 23 GiB (see
   [[project_tinylang_bench_headless_option]]), so 32K ctx can fit without KV thrash.

## What we've tried — verdict (read before re-running anything)

**Clearly NOT going to work (stop trying these):**
- **14B-class models for this agent-loop benchmark.** Qwen2.5-Coder-14B = 0/116
  (stub-and-done, gives up early, 29 min); qwen3-14b base aborted phase 1 (reasoning-format
  parser 500s + overwrite cascade). The harness is clean; the gap is model effort. Don't
  spend more time at 14B. See [[project_tinylang_bench_14b_class]].
- **Naively tuning `--ctx-size` to fix the 32B.** 32K → KV thrash + 2–5 h/phase; 16K →
  conversation overflows the window by phase 3 (`request 16718 tokens exceeds 16384`).
  Neither size is right on a 32 GB box; ctx is not the real lever (see below).
- **Running the 32B at 32K alongside the macOS GUI + Docker** — wired pins at ~23 GiB,
  compressor climbs to ~4.8 GB, throughput collapses over a long run.

**Promising (pursue these):**
- **Qwen2.5-Coder-32B itself.** It's the FIRST local model that actually engages — hits
  the 80-step implement cap, writes real modules, peak 8 passes (32K phase 4), 6 passes
  (16K phase 3). Worth a proper run once the infra is fixed. See `results/run_32bcoder.md`
  + `results/run_32bcoder16k.md`.
- **Headless boot + service shim** (the forward plan) — removes the GUI/Docker wired-RAM
  overhead so 32K KV fits without thrash. Highest expected payoff.
- **Trimming the harness's accumulated context** — the agent loop keeps system prompt +
  full spec + every tool output verbatim across 33–80 steps; that's what overflowed 16K
  and bloated 32K KV. Truncating/summarizing old tool outputs would fix BOTH the overflow
  and the thrash regardless of ctx. Independent of the headless work and worth doing.

**Open question / not yet diagnosed:**
- The `peg-native` tool-call 500 on large `write_file` content (15+ in the 32K run) did
  NOT recur in the 16K p1–3 probe (0 of them) — unclear if that's because early-phase
  files are smaller or ctx-related. Re-check with a LARGE-write smoke test before trusting
  it. The small `ls` smoke test passed and hid the issue last time.

## Setup that's already in place / proven (for when we return)

- Model pulled: `Qwen2.5-Coder-32B-Instruct-Q4_K_M.gguf` on the 2 TB drive at
  `/opt/storage/docker-models/blobs/sha256/8e2fd78ff55e...`. `~/.docker/models` is a
  symlink to `/opt/storage/docker-models` (see [[project_docker_store_opt_storage]]).
  The 86 GB `~/.docker/models.bak` backup was deleted (internal disk freed to ~108 GiB).
- Drivers (committed): `run_32bcoder_1_to_12.sh` (full, 32K) and
  `run_32bcoder16k_1_to_3.sh` (probe, 16K). Both bypass LiteLLM via
  `LITELLM_URL=http://127.0.0.1:8083/v1`, `tool_choice=required` via `--extra-body-json`,
  `LITELLM_ID=qwen2.5-coder-32b`, per-phase commits.
- llama-server launch: `llama-server -m <blob> -a qwen2.5-coder-32b --port 8083
  -c <16384|32768> -fa on -ctk q4_0 -ctv q4_0 -ngl 999 --jinja` (no `--mlock`,
  no `--reasoning-format`). RSS ~20 GB, wired ~22–23 GiB.
- harness.py fixed: model-B `display` label no longer stale; `--litellm-id` now updates
  `display` so logs name the real model. llama-server + containers are STOPPED.

See [[project_tinylang_bench_14b_class]] for the 14B context and [[project_tinylang_benchmark]].

## Earlier status (superseded)

Sonnet baseline (12/12 phases @ 100% via subagent) is complete and committed.

## Runs on the books

### Run 5 — Qwen2.5-Coder-32B Q4_K_M (`B_32bcoder`) — ABORTED ph9 (2026-05-20)
- ~15 h wall to phase 9/12, then killed. 8 phases committed (`b16ebf4`..`e9554bf`),
  phase 9 partial committed. Peak 8 passes (phase 4). Effective ~0/116.
- Killed by infra: `peg-native` tool-call 500s on large `write_file` content + 32K KV
  thrash (per-phase time 14 min → 4.8 h). First local model that actually engages.
- Full writeup: `results/run_32bcoder.md`. Re-run needs the fixes above first.

### Run 5b — Qwen2.5-Coder-32B @ 16K, phases 1–3 timing probe (`B_32bcoder16k`) (2026-05-21)
- p1–3 in **81 min** (vs ~101 min at 32K) — ~20% faster, wired ~22 GiB, no KV thrash,
  0 `peg-native` 500s. Commits `bcf5484`/`973ab2c`/`4bb03ca` + driver `7f297c8`.
- **But 16K is too small:** phase 3 overflowed the window (`request 16718 tokens exceeds
  16384`) → `api_error`. Confirms ctx is not the lever; harness context-trim or headless
  is. Full writeup: `results/run_32bcoder16k.md`.


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
