# qwen3-14b run — aborted after phase 1

Date: 2026-05-19. Branch `test/benchmark-tinylang`. Commit `aa0bad6`.

## Result one-liner

Phase 1 finished with **0 of 11 hidden tests passing** and self-eval ending in `api_error`.
The driver was killed before phase 2 could fully consume hours of compute on the same
failure mode. Total wall on phase 1: 51m 24s (51.4 min).

## Setup

| field | value |
|---|---|
| model | `Qwen_Qwen3-14B-Q4_K_M.gguf` (8.4 GB, Q4_K_M) |
| server | `llama-server` on port 8083, `--ctx-size 32768` (native), no `--mlock` |
| KV cache | q4_0 K/V, flash-attn on |
| harness | `LITELLM_URL=http://127.0.0.1:8083/v1` (LiteLLM bypassed) |
| chat template | jinja, `--reasoning-format deepseek` |
| MAX_TOKENS | 4096 (matches Run 2 capped) |
| label / workdir | `B_14b` / `ModelB_14b/phase_NN/` |

Memory during run: RSS 9.9 GB, system wired ~12.7 GB on a 32 GB box — no kernel-panic
risk, plenty of headroom. The `--mlock` removal worked as intended.

## What happened in phase 1

Two distinct failures interacted to wipe out the phase score.

### 1. The implement step wrote a real lexer, then self-eval clobbered it

From `results/transcripts/phase_01_B_implement.json`:

- step 0: `write_file` Token class only (319 B)
- step 1: `write_file` full lexer with Token + tokenize (5583 B written)
- step 2: `done`

So `implement` finished with a 5.5 KB lexer.py. The model produced a plausible
deliverable.

From `results/transcripts/phase_01_B_selfeval.json`:

- step 0: `pytest -q tests/` → ImportError (tinylang dir missing — the workdir was
  prepared fresh for self-eval; the implement output was supposed to be present, but
  see the next section)
- step 1: `write_file tinylang/lexer.py` with only **117 bytes** — just the `@dataclass
  Token` skeleton, no `tokenize` function. **This obliterated the working implementation.**
- step 2: `mkdir -p tinylang` (no-op)
- step 3: `write_file tinylang/__init__.py` empty
- step 4: `pytest` → still ImportError (no `tokenize`)
- step 5: `edit_file tinylang/lexer.py` with `old_string="@dataclass\nclass Token:"` →
  `new_string` = a TODO-stub tokenize. This deleted the Token class header but left the
  field declarations (`kind: str`, etc.) **after** the new function's `return []`,
  producing an orphan-fields file that is the one we see on disk now.
- step 6: server returned 500 — `Failed to parse input at pos 17226` — the harness
  bailed out with `finish=api_error`.

The model's agent-loop strategy is broken: it did not `read_file` before rewriting, and
its `edit_file` replacement scope was wrong (matched the dataclass header rather than
inserting a function). After step 5 the file is syntactically invalid in a way no test
could possibly pass.

### 2. llama-server reasoning-format parser threw 500s repeatedly

`grep -c "Failed to parse input" qwen3-14b-8083.log` → **12** 500-errors during this
single phase. Positions in the failing payloads were 16k–18k characters, i.e. very
large reasoning blocks. Server log examples:

```
slot release: task 890 | stop processing: n_tokens = 8118, truncated = 0
srv operator(): got exception: {"error":{"code":500,"message":"Failed to parse input at pos 18533: ","type":"server_error"}}
```

The combination `--jinja --reasoning-format deepseek` on qwen3-14b base does not always
emit well-formed reasoning output that llama-server's parser can consume. When the model
produces a long-but-structurally-odd `<think>` stream (or interleaved tool-call
fragments) the parser refuses with 500. The harness catches this and records
`finish=api_error`, but the chain of repair attempts inside self-eval still gets to
write garbage files in earlier steps before the abort.

## Comparison to prior runs (phase 1 only)

| run | model | phase-1 passed | wall | finish |
|---|---|---|---|---|
| Run 2 `B_capped` | qwen3-coder-30b Q4_K_M | 11/11 | ~22 min | done |
| Run 3 `A_subagent` | Sonnet 4 via Claude Code | 11/11 | ~3.4 min | done |
| **This run `B_14b`** | qwen3-14b Q4_K_M | **0/11** | **51 min** | **api_error** |

Sonnet baseline elapsed for the same phase via subagent: 204s. qwen3-coder-30B was about
6× slower than Sonnet but produced the same code. qwen3-14B base is **15× slower than
Sonnet and produces nothing usable.**

## Why we didn't run all 12

Continuing would have:
- Seeded phase 2 from the broken phase 1 workdir → guaranteed cascade.
- Burned ~6–10 h of wall to confirm the obvious: this model + this harness + this
  reasoning-format wrapping doesn't produce working code.

The decision-relevant data was already in phase 1.

## What this says about the hypothesis under test

From `SESSION_STATE.md`:
> Hypothesis to test: smaller model + more KV headroom may hold accuracy past phase 5
> where qwen3-coder-30b's accuracy fell off.

This run does **not** invalidate that hypothesis because phase 1 didn't fail from
context degradation — it failed from **agent-loop / self-eval misuse and reasoning-format
parser instability**. qwen3-14b is the wrong candidate for this hypothesis: it is a
general-purpose thinking model, not a coder-tuned one, and on a step-by-step tool-use
harness it struggles to mutate files coherently.

A clean rerun of the same hypothesis needs either:
- a coder-tuned 14B (e.g. Qwen2.5-Coder-14B-Instruct), or
- qwen3-14b with the reasoning channel disabled (`enable_thinking=false` via jinja
  kwargs), trading the chain-of-thought for stable tool-use behaviour, plus a larger
  output cap (8192) so any remaining `<think>` segments aren't truncated mid-stream.

## Suggested next experiments

1. **Same harness, qwen3-14b with `/no_think` system tag and `MAX_TOKENS=8192`.**
   Removes the parser-500 root cause and the over-long-reasoning blowups.
2. **Pull `Qwen2.5-Coder-14B-Instruct-Q4_K_M`** (~9 GB) as a coder-tuned counterpart and
   rerun. This is the apples-to-apples 14B coder for comparing against qwen3-coder-30B.
3. **Add a self-eval guardrail in `harness.py`** that requires the model to `read_file`
   any file it is about to `write_file` over. The current 14B failure (rewrite-without-
   read) would also be a real risk on any weaker model and is harness-fixable.

Item 3 is independently useful for any future benchmark run regardless of model choice.
