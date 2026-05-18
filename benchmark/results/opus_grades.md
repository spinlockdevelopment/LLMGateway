# Opus grades — phases 1 to 3

Benchmark run 2026-05-18. Models under test:
- **Model A** = Sonnet 4 (`claude-sonnet` via OpenRouter through LiteLLM)
- **Model B** = local-coding qwen3.6-35b (llama-server on M4 :8082, reasoning-format=deepseek)

Run halted after Phase 3 cross-eval. Local model wall-clock was ~30× Sonnet's by
Phase 3 (4.4h implement vs 2.3min). Run-all was killed before Phase 4. See
[NEXT_RUN.md](NEXT_RUN.md) for the design changes for the rerun.

Grading scale: 0–100 on each of two axes per phase. **Accuracy** is grounded
in `pytest -q` results from the workdir. **Completeness** is my (Opus) read of
the implementation against the phase brief — coverage of edge cases, error
messages, code organization, and features the tests don't exercise.

---

## Phase 1 — Lexer

| | Sonnet 4 | local-coding |
|---|---|---|
| Acceptance tests | **11/11 pass (100%)** | 8/11 pass (73%) |
| Failures | — | `test_multi_char_punct`, `test_comments_stripped`, `test_line_col_tracking` |
| Implement steps / time | 15 / 60.5s | 8 / 100.1s |
| Self-eval steps / time | 20 / 58.9s | 28 / 215.9s |
| Tokens in / out | 221k / 6.6k | 195k / 7.2k |
| Cross-eval received | A→B: 75/70 | B→A: 90/85 |

**Opus accuracy A: 95.** Tests are perfect; brief is followed. -5 because the
unknown-char error message is a plain `Exception` (allowed by the brief, but
indistinguishable from internal errors — phase 10 will need a rewrite).

**Opus completeness A: 90.** Token dataclass with the right fields, all token
kinds, multi-char punct, escapes, line/col tracking, comments — all present.
Code organization is clean.

**Opus accuracy B: 55.** Three real bugs in the visible scope:
1. Multi-char punctuation operators (`==`, `!=`, `<=`, `>=`, `&&`, `||`) are
   not lexed as single tokens — `&` is reported as an unrecognized character.
2. `//` comments are not stripped — `&&` again because the second `/` then `/`.
   (Actually the comment test fails for the same reason: `//` is not a token,
   so the lexer chokes on `/` after `/`.)
3. Line/column tracking is incorrect for tokens following a newline (off by
   one in `col`).

These three bugs cascade through every later phase that uses `&&`, `||`, or
comments. They were the root cause of 5 of the 5 Phase-3 failures.

**Opus completeness B: 50.** All required tokens kinds exist, but the operator
set and comment handling are incomplete. Code organization is OK; size is
similar to Sonnet (189 vs 167 LOC). Some defensive scaffolding that wasn't
asked for. **The model also wrote `test_lexer_simple.py` at workdir root** — a
self-test it forgot to delete; pytest then double-counts.

---

## Phase 2 — Parser → AST

| | Sonnet 4 | local-coding |
|---|---|---|
| Acceptance tests (cumulative) | **24/24 (100%)** | 21/25 (84%; 1 carry-over scratch) |
| New phase-2 tests passed | 13/13 | 12/13 (lost `test_comparison_and_logical`) |
| Implement steps / time | 50 / 289s | 29 / 395s |
| Self-eval steps / time | 22 / 75s | 40 / 282s (**hit step cap**) |
| Cross-eval received | A→B: 75/80 | B→A: 95/90 |

**Opus accuracy A: 98.** All AST node names match the contract; all 13 new
parser tests pass; precedence and associativity correct; `else if` chains
work; trailing commas in literals are tolerated; index/call chaining parses
correctly. -2 because parse errors are still untyped (phase 10 territory).

**Opus completeness A: 92.** Full grammar covered. Some helper helpers in
`parser.py` could be tightened but the code is well organized at 402 LOC.

**Opus accuracy B: 65.** Parser works for most constructs but the
`comparison_and_logical` test still fails because the underlying lexer cannot
tokenize `&&`. Sonnet's cross-eval also flagged that `parse_statement`
incorrectly checks for `"{"` as a keyword instead of a punctuation token — a
real concern about the public-contract surface (string match instead of token
kind match).

**Opus completeness B: 70.** All required AST node names are present in
`ast.py` (115 LOC, smaller than Sonnet's 150 LOC but adequate). Parser covers
the grammar at 365 LOC. Notable gaps: `else if` chaining works, but error
recovery is shallow. The lexer-cascade bug from Phase 1 keeps biting.

---

## Phase 3 — Evaluator (arithmetic, booleans, print)

| | Sonnet 4 | local-coding |
|---|---|---|
| Acceptance tests (cumulative) | **39/39 (100%)** | 34/40 (85%; 1 carry-over scratch) |
| New phase-3 tests passed | 15/15 | 14/15 (lost `test_logical_short_circuit_returns_operand`) |
| Implement steps / time | 41 / 136s | 38 / **15,730s (4h22m)** |
| Self-eval steps / time | 16 / 58s | 40 / 7,057s (**hit step cap, 2h**) |
| Cross-eval received | A→B: 85/80 | B→A: 30/40 |

**Opus accuracy A: 99.** Tests perfect; print formatting matches the brief
(integers without `.0`, strings without quotes, booleans lowercase, nil as
`nil`); short-circuit operators return the operand value not a bool. -1 only
because `evaluator.py` runs everything as eager evaluation with no internal
TCO — fine here, but worth noting for phase 6.

**Opus completeness A: 92.** `run()` interface matches the brief.
String-concat handled, mixed-type `+` correctly errors, comparison cross-type
errors correctly, divide-by-zero errors correctly. Captured output is built
via a list-of-strings buffer — clean.

**Opus accuracy B: 70.** 14 of 15 phase-3 tests pass; the one failure is
`test_logical_short_circuit_returns_operand`, again rooted in the lexer not
tokenizing `&&`. The evaluator itself handles arithmetic, comparisons, and
print formatting correctly for everything that lexes. -30 because that single
issue blocks any program using boolean operators.

**Opus completeness B: 68.** `run()` exists and returns captured output.
`builtins.py` is short (19 LOC) but functional — `print` formatting follows
the brief. Code organization at 214 LOC is comparable to Sonnet's 193.
Logical short-circuit semantics weren't reached because the lexer never
emitted `&&` tokens.

**Notable: qwen's cross-eval of Sonnet (B→A: 30/40) is a hallucination.**
qwen claimed Sonnet's `evaluator.py` is "missing the required `run` function"
and "has syntax errors" — neither is true; the file is 193 lines of clean
working code with a top-level `run`. This is a reliability finding about
qwen-as-reviewer, not about Sonnet's code.

---

## Cumulative scoreboard (phases 1–3)

| | Sonnet 4 | local-coding |
|---|---|---|
| Tests passed cumulative | **39 / 39 (100%)** | 34 / 39 (87%) |
| Total tool-call steps | 178 | 218 |
| Total wall time | **685s (11.4 min)** | 23,773s (**6.6 hours**) |
| Total input tokens | ~1.86M | ~1.86M |
| Total output tokens | ~40k | ~32k |

**Opus accuracy avg: A 97 / B 63.**
**Opus completeness avg: A 91 / B 63.**

### Cross-eval received

| Phase | A→B (Sonnet reviewing qwen) | B→A (qwen reviewing Sonnet) |
|---|---|---|
| 1 | 75 / 70 | 90 / 85 |
| 2 | 75 / 80 | 95 / 90 |
| 3 | 85 / 80 | 30 / 40 |
| **mean** | **78 / 77** | **72 / 72** |

Sonnet's reviews are short but consistently identify real defects. qwen's
reviews are short and inconsistent: very generous on phases 1–2, severely
hallucinatory on phase 3.

---

## Findings

1. **Sonnet 4 is dominant on this benchmark so far** — perfect acceptance
   accuracy through three increasingly complex phases, ~30× faster, and more
   reliable as reviewer.

2. **qwen3.6-35b's failures cascade.** A single root cause (missing `&&`,
   `||`, `//` in the Phase 1 lexer) accounts for 4 of its 5 cumulative test
   failures across phases 1–3. The self-eval loop could have caught and fixed
   this, but it ran out of step budget chasing other things first.

3. **Reasoning-mode latency is the dominant cost on the local side.** Wall
   time per tool call grew 30× between phases 1 and 3 as context filled with
   carry-forward files + tool transcripts. `--reasoning-format deepseek` emits
   long `<think>` blocks before every response.

4. **qwen-as-reviewer is unstable.** Phase 1 and 2 scores were generous
   (90/85, 95/90) toward genuinely-passing code. Phase 3 score was 30/40
   citing missing functions that exist. Cross-eval scores from B are not
   reliable signal in this configuration.

5. **The self-eval step cap (40) is the right size for Sonnet** (only used
   16–22 steps) **but too tight for qwen** (hit cap on phases 2 and 3, with
   real failures still present). Phase 3 in particular spent 2 hours
   thrashing inside the cap without getting back to fix the Phase-1 lexer.

See [`results/timings.csv`](timings.csv) for raw numbers.
