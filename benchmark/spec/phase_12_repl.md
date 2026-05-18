# Phase 12 — CLI and REPL

Read `spec/overall_brief.md` first.

## Goal

Wrap the language in a usable command-line tool.

## Scope

- Produce `tinylang/cli.py` with a `main(argv: list[str] | None = None) -> int`
  function. It is the entry point. Tests will call it directly with various
  argv lists.
- Produce a shim script `tinylang_cli.py` at the workdir root that calls
  `tinylang.cli.main()` so the binary is invokable via
  `python tinylang_cli.py ...`. (Avoid relying on console-script entry-points;
  tests run via `python tinylang_cli.py`.)

## Subcommands

```
python tinylang_cli.py run <file.tl>        # execute the file
python tinylang_cli.py check <file.tl>      # parse only, print "ok" or errors
python tinylang_cli.py                      # enter REPL
python tinylang_cli.py repl                 # also enters REPL
```

### `run`

- Read file. Execute via the same evaluator as `run()`. Print captured output
  to real stdout.
- On `TinylangError`, print the error (with `traceback()` for runtime errors)
  to stderr. Exit code 1 on error, 0 on success.
- If file does not exist, print a message to stderr and exit 2.

### `check`

- Parse only. Print `ok` and exit 0 on success.
- Print parse error to stderr and exit 1 on failure.

### `repl`

- Prompt is `>>> `; continuation prompt for multi-line is `... `.
- A line ending with an opening unbalanced `{` or `(` or `[` indicates a
  multi-line input — keep reading until the brackets balance, then evaluate.
- For each balanced input:
  - If it parses as an expression, evaluate it and print the result using the
    same `print`-formatting rules as the runtime (or, equivalently,
    `repr`-style for strings — your call, but be consistent).
  - If it parses as a statement, execute it; print captured output if any.
  - On error, print the error to stderr; the REPL continues to the next
    prompt.
- `Ctrl-D` (EOF) ends the REPL cleanly with exit code 0.
- The REPL maintains one persistent global environment across inputs. State
  persists.

## Public surface

```python
from tinylang.cli import main
main(["run", "hello.tl"])           # returns int exit code
main(["check", "ok.tl"])            # returns int exit code
main(["repl"])                      # blocks for stdin
```

## Tests

Tests invoke `main(...)` with synthetic argv lists, capturing stdout/stderr.
For the REPL test, stdin is replaced with a `StringIO` of input lines and the
test checks the prompt-and-response output.

## Out of scope

- Tab completion.
- History persistence to disk.
- Color output.
