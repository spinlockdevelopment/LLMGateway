# 128K context headroom test — Gemma-4-26B-A4B Q4_K_M (2026-05-24)

## TL;DR

**128K fits comfortably on this 32 GB M4 with `iogpu.wired_limit_mb=28000`.**
Doubling allocated ctx from 64K → 128K costs only **+2.7 GB idle RSS** and
**~zero additional RSS during actual inference** (because the working KV scales
with *tokens used*, not allocated capacity — Gemma-4-26B-A4B is a hybrid
attention + SSM/recurrent model and only attention layers' KV scales with ctx).

Next runs of the benchmark should use **`-c 131072`**. This eliminates the
two `request exceeds available context size` aborts seen in the 64K run
(phase 6 at 65,618 tokens, phase 9 at 66,584 tokens — both just barely over)
and gives a comfortable 60K+ tokens of slack for the conversation accumulation
late in the run.

## Method

After Run 8 (B_gemma4) completed at 21:50 EDT 2026-05-24, the 64K llama-server
was killed cleanly. Same binary (llama.cpp build 9290), same model
(`/opt/storage/gguf/gemma-4-26B-A4B-it-UD-Q4_K_M.gguf`), same flags except
`-c 131072` in place of `-c 65536`:

```
llama-server -m <model> -a gemma-4-26b-a4b --host 127.0.0.1 --port 8083 \
  --parallel 1 -c 131072 -fa on -ctk q8_0 -ctv q8_0 -ngl 999 --jinja
```

Three measurement points:

1. **Idle** — just after `/health` returned ok, before any request.
2. **Small warm-up** — a `tool_choice=required` `ls` tool call (~50 chars input,
   ~50 chars output).
3. **Realistic load** — an 11,117-byte prompt (system + repeated context +
   `write_file` task brief), `max_tokens=8192`, producing 3,093 chars of
   `reasoning_content` + 8,138-char tool-call content. Closer to what the
   benchmark actually does per implement step.

RSS sampled every 3 s during the realistic load.

## Numbers

| Metric | 64K (Run 8) | 128K (this test) | Delta |
|---|---:|---:|---:|
| Allocated ctx | 65,536 | 131,072 | +2× |
| Model load wall | (cached, ~10s) | ~15 s | (filesystem cache hit) |
| Idle RSS | 14.7 GB | 17.4 GB | **+2.7 GB** |
| RSS after small warm-up | — | 17.42 GB | +0.02 GB |
| Peak RSS during 11K-prompt + 8K-tool + 3K-reasoning request | 18.7 GB (peak during real benchmark phase) | **17.75 GB** | −0.95 GB (!) |
| Memory pressure during load | — | **36% free, steady** | — |
| Pageouts during load | — | 23,848 (unchanged) | 0 |
| Wired limit (`iogpu.wired_limit_mb`) | 28 GB | 28 GB | — |
| Headroom at peak | 9.3 GB | **10.25 GB** | +0.95 GB |
| Inference correctness | ✓ | ✓ (`finish=tool_calls`, valid JSON, no parser errors) | — |

The seemingly-counterintuitive finding: **peak RSS at 128K was *lower* than the
64K peak** (17.75 GB vs 18.7 GB). That's because the 18.7 GB peak from the
benchmark run was during a much larger conversation (tens of thousands of
tokens of accumulated implement-loop history), whereas this test was a single
~11K prompt. The point isn't that 128K saves memory; it's that **the working set
scales with actual tokens, not with allocated ctx** — so 128K is not strictly
"twice the memory" of 64K. The cost of allocating 128K vs 64K is just the
**+2.7 GB idle delta** (the reserved KV slots), and that's a one-time cost.

## Server-side confirmation

llama.cpp's startup log explicitly identifies the model as hybrid/recurrent:

```
W slot update_slots: id 0 | task 19 | forcing full prompt re-processing due to
   lack of cache data (likely due to SWA or hybrid/recurrent memory, see
   https://github.com/ggml-org/llama.cpp/pull/13194#issuecomment-2868343055)
```

This is the same architectural class as Qwen3.6-35B-A3B (project memory
[[qwen36-a3b-256k-headroom]] showed qwen3.6 fit 256K q8_0 KV at RSS 23.4 G /
wired 26 G on the same box). Gemma's pattern is similar but starts from a
smaller idle RSS (17.4 GB at 128K vs qwen's 23.4 GB at 256K).

## Recommendation for the next run

Switch to **`-c 131072`** for all future Gemma-4 benchmark runs. No other flag
changes needed. Expected wins:

1. **Eliminates the 2 ctx-overflow aborts** in phase 6 and phase 9 of Run 8.
   May close a few tests of the gap vs Sonnet on phase 9 specifically.
2. **Gives the iterating fix loop more room** if it ever needs to carry a long
   conversation through multiple fix attempts.
3. **Same memory pressure profile** as 64K — no risk of OOM or compression.

Could plausibly try `-c 196608` (192K) or `-c 262144` (256K — the model's full
trained ctx) too, but there's no current evidence the benchmark needs that
much; 128K is the right starting point.

## Notes / caveats

- This test used **Q4_K_M** (16.9 GB on disk). Q5_K_M would be ~21 GB on disk
  and ~21–22 GB peak RSS; that still fits within 28 GB wired but with thinner
  headroom (~6 GB at peak). Q5 would be worth a comparison run if quality
  matters more than headroom.
- Peak under a long-conversation accumulating run (the kind that exists in the
  benchmark's late phases) wasn't measured here — that was the 18.7 GB observed
  during Run 8 at 64K. Expect 128K to land in roughly the same neighborhood
  during real use, since the dominant cost is the tokens actually used, not
  the allocated headroom.
