# Phase 10 — Error model

Read `spec/overall_brief.md` first.

## Goal

Replace ad-hoc exceptions with a structured error model: typed exception
classes, line/column info, and call stack traces for runtime errors.

## Scope

- Produce `tinylang/errors.py` with:

  ```python
  class TinylangError(Exception):
      message: str
      line: int | None
      col: int | None

      def __init__(self, message, line=None, col=None):
          super().__init__(message)
          self.message = message
          self.line = line
          self.col = col

      def __str__(self):
          where = f" at line {self.line}, col {self.col}" if self.line else ""
          return f"{self.message}{where}"

  class LexError(TinylangError): pass
  class ParseError(TinylangError): pass
  class TinyRuntimeError(TinylangError):
      # has an optional `stack` attribute: a list of frame dicts
      # [{"fn": "<name>", "line": int}, ...] outermost first
      stack: list
  ```

- Rewire the lexer to raise `LexError`, the parser to raise `ParseError`, and
  the evaluator to raise `TinyRuntimeError` for any tinylang-level error.
- `TinyRuntimeError.stack` is populated as the error unwinds through `Call`
  frames in the evaluator. Each frame records the function name (or
  `"<anonymous>"` for an `FnLit` that has no name) and the line of the call
  site.
- The exception `__str__` should always be informative enough to debug from.
  For runtime errors with a stack, also include a `traceback()` method or
  property that returns a multi-line string of the form:

  ```
  RuntimeError: undefined variable 'foo' at line 7, col 3
    in <anonymous> at line 5
    in main at line 1
  ```

  The exact wording is up to you; tests check that the function names and the
  word "line" appear.

## Required behaviors

- Calling `tokenize("@")` raises `LexError` whose `str()` includes `line` and
  `col`.
- Calling `parse("let x = ;")` raises `ParseError` with line/col.
- `run("print(foo);")` raises `TinyRuntimeError` mentioning `foo`.
- `run("fn f() { return g(); } fn g() { return h(); } fn h() { return missing; } f();")`
  raises `TinyRuntimeError` whose `stack` lists `h`, `g`, `f` (innermost
  first) — or `f`, `g`, `h` outermost first; either convention is fine, but
  pick one and document it in `errors.py`.

## Public surface

- `run(source: str) -> str` still returns captured output. If the program
  errors, `run` raises a `TinylangError` subclass. It does **not** print the
  traceback by itself — the CLI in phase 12 will format it for display.

## Out of scope

- Custom user-throwable error types in tinylang code (no `throw` statement).
- Recovering from errors and continuing execution.
