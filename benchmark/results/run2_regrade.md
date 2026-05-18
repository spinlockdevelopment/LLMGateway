# Run 2 regrade — clean pytest pass rates after litter strip

Scratch files at each workdir root (`debug_*.py simple_*.py minimal_*.py
detailed_*.py very_*.py final_*.py test_*.py`, excluding the Phase-12
deliverable `tinylang_cli.py`) were deleted in one pass. Numbers below are
from `pytest -q tests/` against the cleaned snapshots; results were
identical when `pytest tests/` was scoped explicitly before the strip, so
the litter was a collection-noise issue, not a true-failure issue.

## True pass rates — local-coding qwen3.6-35b

| Phase | Pass | Fail | Coll-error | Total | % | Notable |
|---|---|---|---|---|---|---|
| 01 | **11** | 0 | 0 | 11 | **100%** | unchanged from Run 1 capped snapshot |
| 02 | 14 | 10 | 0 | 24 | 58% | parser regressions: `else if`, `for`, dict/list literals, index chains |
| 03 | 15 | 24 | 0 | 39 | 38% | cumulative loss — Phase-2 parser bugs cascade |
| 04 | 0  | 0  | 4 | 47 | **0%** | **`tinylang.evaluator.run` removed** — every test module fails to import |
| 05 | 18 | 37 | 0 | 55 | 33% | `run` restored somehow; tests collect again |
| 06 | 21 | 44 | 0 | 65 | 32% | |
| 07 | 21 | 50 | 0 | 71 | 30% | |
| 08 | 23 | 59 | 0 | 82 | 28% | |
| 09 | 25 | 67 | 0 | 92 | 27% | |
| 10 | 0  | 0  | 10 | 99 | **0%** | **`tinylang/errors.py:18` SyntaxError** — `f"{type(self).__name__)}: ..."` (stray `)` in f-string). Every module that imports `tinylang.errors` (i.e. all of them) blows up at collection. |
| 11 | 18 | 91 | 0 | 109 | 17% | |
| 12 | 23 | 93 | 0 | 116 | 20% | CLI structurally present (`tinylang/cli.py` + `tinylang_cli.py` shim) but only 1/7 CLI tests pass — parser+evaluator too broken for real programs |

## What the regrade actually proved

1. **The in-run numbers in `run2_summary.md` were an underestimate by
   only a small margin for most phases.** Stripping the litter recovered
   ~4–8 hidden passes per phase (where collection had been aborting after
   one bad scratch test file), but did not change the qualitative picture:
   the model was failing 70%+ of acceptance tests from Phase 5 onward.

2. **Two phases (04, 10) are catastrophic regressions of the deliverable
   itself, not litter artefacts.**
   - Phase 04: the model removed `run` from `tinylang/evaluator.py`. The
     re-exporting `from .evaluator import run` in `tinylang/__init__.py`
     remained, so every test that does `from tinylang import …` or
     `from tinylang.evaluator import run` errors at import time. `run`
     was a Phase 3 deliverable; the model destroyed it during Phase 4's
     `if`/`while` work.
   - Phase 10: the model wrote a Python `SyntaxError` into the deliverable.
     `f"{type(self).__name__)}: {self.message}"` — closing `)` inside the
     interpolated expression has no matching `(`. The file never imports.
     Self-eval did not catch this; the model exhausted its 5-step
     `implement` budget on an api_error retry and never returned.

3. **Even after litter strip, scratch `.tl` test inputs and `.py.backup`
   files were left in workdir.** `basic_test.tl final_test.tl
   minimal_test.tl simple_test.tl test_dict.tl` (phases 9–12) and
   `tinylang/ast.py.backup` (phases 9–12). They don't affect pytest so
   were not stripped, but the harness-cleanup work in `run2_summary.md`
   should sweep them too.

4. **Phase 12 CLI**: the shim and `tinylang/cli.py` both exist and have
   plausible structure (subcommand dispatch, REPL skeleton). 1 of 7 CLI
   acceptance tests passes — `test_run_file_not_found` (because returning
   exit-code 2 from a nonexistent path doesn't require the evaluator to
   work). All six tests that actually execute or parse a `.tl` program
   fail downstream of the parser regressions.

## Litter strip — what was removed

11 phases (02–12), 9–15 scratch files per phase, all from the workdir
root only. Pattern: `debug_*.py simple_*.py minimal_*.py detailed_*.py
very_*.py final_*.py test_*.py` excluding `tinylang_cli.py`.

`.tl` and `.py.backup` scratch were left in place — they are not pytest
hazards. A future harness change should `git clean -fd` between phase
seeds to drop them too.
