# 128K re-run partial — Gemma-4-26B-A4B Q4_K_M, phases 1–10 (B_gemma4_128k)

Stopped by user at phase 11 start. Same model and binary as Run 8 (B_gemma4),
**only `-c 65536` → `-c 131072` changed**. All other flags, prompts, harness, and
driver shape identical.

## TL;DR — 128K made the model WORSE, not better

Three findings, each contrary to the going hypothesis going in:

1. **128K is ~15% FASTER overall** (11.8 h vs 14.0 h for phases 1–10), not slower.
   Counter to what longer reasoning windows usually imply.
2. **128K is dramatically WORSE on pass counts from phase 4 onward.** Phase 10
   went from 86/13 at 64K to **28/71 at 128K**, regressing 23 previously-passing
   tests. The gap to Sonnet *widens* from −13 to −71 on that phase alone.
3. **Memory pressure is fine.** Pageouts rose only 8K during the 12.5 h run;
   no OOM, no wired-limit hits. The 128K headroom test was honest.

So the box has plenty of room for 128K but the model can't use it well.

## Pass count comparison (apples-to-apples, phases 1–10)

| phase | Sonnet | 64K (Run 8) | 128K (this) | 128K delta vs 64K | 128K total tests | 128K gap vs Sonnet |
|---:|---:|---:|---:|---:|---:|---:|
| 01 |  11 / 11 |  11 / 0  ✓ |  **11 / 0**  ✓ | 0 | 11 |   0 |
| 02 |  24 / 24 |  12 / 12   |  **22 / 2**    | **+10 ⭐** | 24 |  −2 |
| 03 |  39 / 39 |  39 / 0  ✓ |  **39 / 0**  ✓ | 0 | 39 |   0 |
| 04 |  47 / 47 |  47 / 0  ✓ |  **42 / 5**    |   −5  | 47 |  −5 |
| 05 |  55 / 55 |  55 / 0  ✓ |  **42 / 13**   |  −13  | 55 | −13 |
| 06 |  65 / 65 |  65 / 0  ✓ |  **45 / 20**   |  −20  | 65 | −20 |
| 07 |  71 / 71 |  71 / 0  ✓ |  **45 / 26**   |  −26  | 71 | −26 |
| 08 |  82 / 82 |  78 / 4    |  **47 / 35**   |  −31  | 82 | −35 |
| 09 |  92 / 92 |  83 / 9    |  **49 / 43**   |  −34  | 92 | −43 |
| 10 |  99 / 99 |  86 / 13   |  **28 / 71 ⚠** |  −58  | 99 | −71 |

Phase 2 alone improved (+10 tests). Phase 10 catastrophic: the model broke 23
previously-passing tests AND failed most of the new ones.

## Wall time comparison (phases 1–10)

| phase | 64K wall (min) | 128K wall (min) | diff |
|---:|---:|---:|---:|
| 01 |  48.1 |  60.5 | **+26%** |
| 02 | 171.0 | 126.5 | −26% |
| 03 | 114.3 |  88.4 | −23% |
| 04 |  72.7 | 101.4 | **+40%** |
| 05 |  53.8 |  66.0 | **+23%** |
| 06 |  87.0 |  37.6 | −57% |
| 07 |  29.7 |  35.7 | +20% |
| 08 |  96.1 |  36.7 | **−62%** |
| 09 |  85.2 |  89.8 |  +5% |
| 10 |  80.2 |  67.6 | −16% |
| **TOTAL** | **838.1 m** | **710.3 m** | **−15%** |

The high-variance per-phase deltas are revealing. The "faster" phases (6, 8) are
*faster because the model gave up sooner*: fewer pass count, less iteration
traction, no-progress rule fires earlier and quits. The "slower" phases (4, 5)
are slower because the fix iteration spun harder (phase 4 fix_01 was 4,671 s)
without making progress.

## Finish-reason distribution (phases 1–10)

|  | 64K (run 8 over all 12 phases) | 128K (run 9, phases 1–10) |
|---|---:|---:|
| `done`     | 17 | **5**  |
| `step_cap` | 11 | **23** |
| `api_error`|  9 |  1     |

Reading this: at 128K, the model **stops calling `done`** (5 vs 17) and instead
**grinds at the step cap** (23 vs 11). The api_error reduction is real (one
overflow gone, fewer truncations) but the gain is dwarfed by the model's
inability to wind down. With more context it just keeps rambling.

## Memory pressure (the question that motivated the run)

| Metric | Before 128K run | After 128K run (12.5 h elapsed) |
|---|---:|---:|
| Pageouts | 23,848 | 31,984 (**+8,136**) |
| Server RSS | 17.4 GB (post-load idle) | **19.22 GB** (working set) |
| Memory free | 92% (post-kill state) | 23% |
| OOM events in log | 0 | **0** |
| `iogpu.wired_limit_mb` hits | 0 | **0** |

8K new pageouts over 12.5 hours is normal background system activity (not
compression pressure caused by the model). Server RSS bumps from 17.4 GB idle
to 19.22 GB under real workload — a +1.8 GB working-set delta, well within the
10+ GB headroom. **Memory was never the limiting factor.** The headroom test
was honest; we have room. We just shouldn't use it.

## Why does 128K make Gemma worse here?

Likely combination, in plausibility order:

1. **More room → longer `<think>` blocks → diluted reasoning.** Gemma-4 emits
   `reasoning_content` before tool calls. At 64K the implicit pressure to be
   concise was a useful constraint. At 128K the model thinks more, branches
   more, and the actual decision gets weaker — same dynamic as a human writing
   a 5-paragraph plan vs writing a 30-paragraph plan for the same task.

2. **Accumulated conversation cruft.** Each implement-loop turn carries
   forward all prior tool outputs + assistant messages + their reasoning.
   With more headroom the harness's auto-truncation doesn't fire, so the model
   sees a longer noisier history each turn and signal-to-noise drops as the
   phase progresses.

3. **Possibly RoPE / attention scaling regime change.** Gemma-4-26B-A4B is
   trained on 256K so 128K is well within range, but the *operating regime* at
   128K may differ from 64K (different default RoPE base, different attention
   sink behavior in the SSM/attention hybrid). Hard to isolate without ablation.

The phase-2 improvement (+10) is interesting — it's the one phase where the
64K run had ambiguous problems too. Likely 128K gave it just enough room to
work through what the 64K run couldn't. But beyond phase 2 the extra room is a
net negative.

## Recommendation

**Use 64K (`-c 65536`) for production benchmark runs.** 128K is documented as a
safety margin for the rare overflow case but should NOT be the default. If a
future run hits a ctx-overflow at 64K, the cleanest fix is the **harness-level
truncation of accumulated tool outputs** (already in the SESSION_STATE forward
plan) rather than bumping the ctx allocation.

128K headroom result (`results/headroom_128k_gemma4.md`) stays valid — the box
*can* hold it. We just learned that holding it costs us pass count.

## State on disk

- Phases 1–10 committed: `2e79f7b..4425243` (label `B_gemma4_128k`).
- Driver log: `/tmp/run_gemma4_128k_driver.log`.
- Per-phase logs: `benchmark/results/run_gemma4_128k/phase_*.harness.log`,
  `..._fix_*.log`.
- Iterations table: `benchmark/results/run_gemma4_128k/iterations.tsv`.
- Phase 11 was in implement when the user stopped the run; no commit.
- Server pid 76055 still up at 128K; harmless to leave or kill.
