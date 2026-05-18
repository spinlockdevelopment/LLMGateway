# A/B/C reasoning experiment — Phase 1 only, local model

Three variants of `local-coding` (qwen3.6-35b on `llama-server` :8082) run
against Phase 1 (lexer) of the tinylang benchmark. Same brief, same tests,
same harness, same step caps.

| Variant | extra_body | max_tokens | Implement (steps / s) | Self-eval (steps / s) | Final pytest | Total wall |
|---|---|---:|---|---|---|---:|
| `thinkon`  | none (default = thinking on) | 4096 | 18 / 157s | 40 / 553s (**step_cap**) | 10 pass, 1 fail | **711s** |
| `thinkoff` | `enable_thinking=false` | 4096 | 12 / 119s | 20 / 218s (done) | 8 pass, 3 fail | **338s** |
| **`capped`** | none (thinking on) | **2048** | 12 / 99s | 36 / 563s (done) | **11 pass, 0 fail** | **662s** |

## Findings

1. **`capped` wins on both axes.** Perfect 11/11 accuracy and slightly *faster*
   than `thinkon` overall (662s vs 711s). Lower max_tokens prevents the model
   from emitting overly long `<think>` blocks on simple steps — the model
   reasons enough to be useful, but doesn't ramble. Self-eval also completed
   in 36/40 steps instead of hitting the cap.

2. **`thinkoff` is 2.1× faster than `thinkon` but loses 2 more tests.**
   The model handles boilerplate-level coding fine without thinking, but the
   debug-and-fix loop in self-eval suffers — it identifies failures but
   can't reason through fixes for the multi-character punctuation and
   line/col bugs that need careful tracking.

3. **The first-run baseline (which had similar config to `thinkon`) was
   8/11 in 532s.** This run's `thinkon` is 10/11 in 711s — similar
   ballpark, with run-to-run noise.

## Recommendation for the 12-phase rerun

Use **`capped`**: keep `local-coding` (thinking on) but set
`MAX_TOKENS = 2048`. It gives the best accuracy-per-second of the three
variants. There's a real chance the win is Phase-1-specific (carryforward
context is small here), so the same A/B/C experiment is worth re-running on
Phase 6 (functions) or Phase 10 (errors), where reasoning matters more —
but for now `capped` is the right default.

Open question for later: try further max_tokens reductions (1024? 1536?) to
see if there's a sharper knee. Also worth testing on the slowest stages.

## What the LiteLLM logs captured

`docker logs llm-gateway` was tee'd to file per variant:

```
results/exp_phase1/thinkon.litellm.log    17 KB
results/exp_phase1/thinkoff.litellm.log   8.5 KB
results/exp_phase1/capped.litellm.log     15 KB
```

These are HTTP-access-log style: each `POST /v1/chat/completions` line plus
metrics scrapes. Good for spotting failed requests and counting calls. They
do **not** include request/response bodies — for that we'd need
`--detailed_debug` or a `success_callback` writing structured logs.

## Files

```
results/exp_phase1/
  RUNNER.log                                   # exp shell script stdout
  thinkon.harness.log     thinkon.litellm.log
  thinkoff.harness.log    thinkoff.litellm.log
  capped.harness.log      capped.litellm.log
  RESULTS.md                                   # this file

ModelB_thinkon/phase_01/   ModelB_thinkoff/phase_01/   ModelB_capped/phase_01/
```

`benchmark/results/timings.csv` has rows tagged `B_thinkon`, `B_thinkoff`,
`B_capped` for the three variants.
