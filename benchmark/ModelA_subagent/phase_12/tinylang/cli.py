"""Phase 12 — command-line interface and REPL for tinylang.

The single public entry point is :func:`main`, which dispatches on the first
positional argument:

* ``run <file.tl>``    — execute the file via the same evaluator as
  :func:`tinylang.evaluator.run`. Captured ``print`` output is forwarded to
  real stdout. A :class:`TinylangError` is rendered to stderr (with a
  ``traceback()`` view for runtime errors) and exits 1; a missing file exits
  2.
* ``check <file.tl>``  — parse-only mode. Prints ``ok`` on success (exit 0)
  or the parse error on stderr (exit 1).
* ``repl`` (or no args) — start an interactive read-eval-print loop with a
  persistent global environment.

The CLI is deliberately thin: every actual language behaviour lives in the
phase-1..11 modules. The job of this module is just argv routing, I/O, and
the REPL's bracket-aware multi-line input loop.

Design notes
------------

* The REPL shares its evaluator/state across inputs. We reuse the same
  ``_Evaluator`` instance for the whole session so ``let`` bindings, function
  definitions, and (importantly) the captured-by-reference environments used
  by closures persist across prompts.
* Each input is *re-parsed* fresh — the parser doesn't have a streaming mode,
  but inputs are small, so re-parsing is fine. Statements appended to the
  evaluator's globals via ``exec_stmt`` are observable on the next prompt.
* To decide whether to print a value, we check the parsed program: if it
  consists of exactly one ``ExprStmt`` and the input was a single line that
  doesn't end in ``;``, we evaluate the expression directly and print its
  value (when not ``nil``). Otherwise we execute as a statement program and
  flush any ``print`` output that accumulated.
* Multi-line detection is bracket-balance based, per the brief: while the
  cumulative balance of ``( [ {`` vs ``) ] }`` is positive (or the line ends
  with a backslash continuation — not in the brief but harmless), we keep
  reading. Strings and ``//`` comments are skipped during the balance scan
  so that ``"{"`` and ``// {`` don't confuse the matcher.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import IO, Optional

from .ast import ExprStmt, Program
from .builtins import format_value
from .errors import ParseError, TinylangError, TinyRuntimeError
from .evaluator import (
    STDLIB_PATH,
    _Evaluator,
    _BreakSignal,
    _ContinueSignal,
    _ReturnSignal,
    _load_stdlib,
)
from .parser import parse


# --------------------------------------------------------------------------- #
# main entry point                                                            #
# --------------------------------------------------------------------------- #


def main(argv: Optional[list] = None) -> int:
    """Dispatch the requested subcommand.

    ``argv`` is the *user* argv — i.e. it does not include ``sys.argv[0]``.
    Passing ``None`` falls back to ``sys.argv[1:]`` so the shim script can
    delegate without slicing.
    """
    if argv is None:
        argv = sys.argv[1:]

    # Bare invocation = REPL. Matches the brief's "python tinylang_cli.py".
    if not argv:
        return _cmd_repl([])

    cmd = argv[0]
    rest = argv[1:]

    if cmd == "run":
        return _cmd_run(rest)
    if cmd == "check":
        return _cmd_check(rest)
    if cmd == "repl":
        return _cmd_repl(rest)

    # Anything else is a usage error. Print to stderr and exit non-zero so
    # shell pipelines notice. Exit code 2 matches conventional CLI tools
    # (``argparse`` uses 2 for usage errors).
    print(
        f"tinylang: unknown command {cmd!r}. "
        "Use one of: run, check, repl.",
        file=sys.stderr,
    )
    return 2


# --------------------------------------------------------------------------- #
# `run <file>`                                                                #
# --------------------------------------------------------------------------- #


def _cmd_run(rest: list) -> int:
    if len(rest) != 1:
        print("tinylang run: expected exactly one file argument", file=sys.stderr)
        return 2
    path = Path(rest[0])
    try:
        source = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        # The brief specifies exit code 2 for a missing file, distinct from
        # the exit-1 used for tinylang-level errors.
        print(f"tinylang: file not found: {path}", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"tinylang: could not read {path}: {e}", file=sys.stderr)
        return 2

    try:
        # Build the evaluator manually so we can write captured output as it
        # accrues — but the existing pattern (run + return string) is the
        # supported public surface, and tests capture stdout via
        # ``capsys``, so a final single ``sys.stdout.write`` is the simplest
        # behaviour and matches what ``run()`` already produces.
        evaluator = _Evaluator()
        _load_stdlib(evaluator, STDLIB_PATH)
        program = parse(source)
        output = evaluator.run_program(program)
    except TinyRuntimeError as e:
        # Runtime errors get the traceback() view so the user sees the call
        # chain too — exactly the contract phase 10 set up.
        print(e.traceback(), file=sys.stderr)
        return 1
    except TinylangError as e:
        # Parse / lex errors render with their own location-aware __str__.
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        return 1

    if output:
        sys.stdout.write(output)
    return 0


# --------------------------------------------------------------------------- #
# `check <file>`                                                              #
# --------------------------------------------------------------------------- #


def _cmd_check(rest: list) -> int:
    if len(rest) != 1:
        print("tinylang check: expected exactly one file argument", file=sys.stderr)
        return 2
    path = Path(rest[0])
    try:
        source = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"tinylang: file not found: {path}", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"tinylang: could not read {path}: {e}", file=sys.stderr)
        return 2

    try:
        parse(source)
    except TinylangError as e:
        # Lex errors are also a "couldn't parse" outcome from the user's POV.
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        return 1
    print("ok")
    return 0


# --------------------------------------------------------------------------- #
# REPL                                                                        #
# --------------------------------------------------------------------------- #


PRIMARY_PROMPT = ">>> "
CONTINUATION_PROMPT = "... "


def _cmd_repl(rest: list) -> int:
    """Run an interactive REPL until EOF.

    ``rest`` is accepted but ignored — the brief doesn't define any flags for
    the ``repl`` subcommand. Tests substitute ``sys.stdin`` / ``sys.stdout``
    with ``StringIO`` instances; we honour the *current* values of
    ``sys.stdin``/``sys.stdout``/``sys.stderr`` rather than caching them at
    import time, so a test can patch them just before calling ``main(...)``.
    """
    # Single evaluator for the whole session so state persists.
    evaluator = _Evaluator()
    _load_stdlib(evaluator, STDLIB_PATH)

    stdin: IO = sys.stdin
    stdout: IO = sys.stdout
    stderr: IO = sys.stderr

    while True:
        try:
            line = _prompt(stdin, stdout, PRIMARY_PROMPT)
        except EOFError:
            # Clean exit on Ctrl-D / closed stdin, per the brief.
            return 0

        if line is None:  # stdin returned EOF without any data.
            return 0

        # An empty line at the primary prompt is a no-op — just re-prompt.
        # (Matches the behaviour of e.g. the Python REPL.)
        if line.strip() == "":
            continue

        # Multi-line: keep reading while brackets remain unbalanced.
        buffer = line
        while _needs_more(buffer):
            try:
                more = _prompt(stdin, stdout, CONTINUATION_PROMPT)
            except EOFError:
                # EOF mid-input: treat as exit, matching most REPLs and the
                # brief's "Ctrl-D ends the REPL cleanly".
                return 0
            if more is None:
                return 0
            buffer = buffer + "\n" + more

        _eval_repl_input(evaluator, buffer, stdout, stderr)


def _prompt(stdin: IO, stdout: IO, prompt: str) -> Optional[str]:
    """Write ``prompt`` to stdout and read one line of input.

    Returns the line *without* its trailing newline, or ``None`` if stdin is
    exhausted with no remaining data. Flushes stdout so the prompt actually
    appears before ``readline`` blocks (important when stdout is line-buffered,
    which is the default for terminals and ``StringIO``-backed test setups).
    """
    stdout.write(prompt)
    stdout.flush()
    line = stdin.readline()
    if line == "":
        # Empty string from readline means EOF.
        return None
    # Strip exactly one trailing newline if present; preserve internal layout.
    if line.endswith("\n"):
        line = line[:-1]
    if line.endswith("\r"):
        line = line[:-1]
    return line


def _eval_repl_input(
    evaluator: _Evaluator, source: str, stdout: IO, stderr: IO
) -> None:
    """Parse + execute one balanced REPL submission.

    Behaviour:

    * Parse failures print to stderr and return — the loop continues.
    * A program of exactly one ``ExprStmt`` is evaluated as a bare expression
      and its value is printed (using ``format_value``) unless the value is
      ``nil``. The expression's side-effects (``print(...)``) still flush.
    * Otherwise every statement is executed; any captured ``print`` output is
      flushed to stdout.
    * Runtime errors print via ``traceback()`` (matches ``run``).
    * Stray ``break`` / ``continue`` / ``return`` at the top level surface as
      runtime errors with a helpful message — same wording as
      ``_Evaluator.run_program`` uses.

    The evaluator's output buffer is *cleared* at the start of every
    submission so that one prompt's prints don't leak into the next prompt's
    expression-value-print step.
    """
    try:
        program: Program = parse(source)
    except TinylangError as e:
        # Both LexError and ParseError land here.
        print(f"{type(e).__name__}: {e}", file=stderr)
        return

    # Fresh output buffer for this submission so we can tell what was printed
    # *this* turn apart from any prior turn's output.
    evaluator.output.clear()

    # Decide whether this is an "evaluate-and-show" expression or a regular
    # statement program. A bare expression in the REPL is parsed as a single
    # ExprStmt — but only when it ends in ``;`` (the parser requires the
    # semicolon). To keep both Python-like (no-semicolon) and tinylang-like
    # (semicolon) inputs ergonomic, we try the source as-is first and, if it
    # fails to parse *and* doesn't already end with a terminator, retry with
    # a trailing ``;``. This block is the *parsed-OK* path.
    is_bare_expr = (
        len(program.stmts) == 1 and isinstance(program.stmts[0], ExprStmt)
    )

    try:
        if is_bare_expr:
            expr = program.stmts[0].expr
            value = evaluator.eval_expr(expr, evaluator.globals)
            # Flush anything the expression itself printed.
            captured = "".join(evaluator.output)
            evaluator.output.clear()
            if captured:
                stdout.write(captured)
            # Show the result, but suppress nil (consistent with the brief's
            # "print the result" — printing ``nil`` for every statement-shaped
            # expression would be noisy).
            if value is not None:
                stdout.write(format_value(value) + "\n")
            stdout.flush()
        else:
            for stmt in program.stmts:
                evaluator.exec_stmt(stmt, evaluator.globals)
            captured = "".join(evaluator.output)
            evaluator.output.clear()
            if captured:
                stdout.write(captured)
                stdout.flush()
    except TinyRuntimeError as e:
        # Drain any partial output the failing statement produced before the
        # error so the user sees their prints in order.
        captured = "".join(evaluator.output)
        evaluator.output.clear()
        if captured:
            stdout.write(captured)
            stdout.flush()
        print(e.traceback(), file=stderr)
    except _BreakSignal:
        print(
            "RuntimeError: 'break' used outside of a loop",
            file=stderr,
        )
    except _ContinueSignal:
        print(
            "RuntimeError: 'continue' used outside of a loop",
            file=stderr,
        )
    except _ReturnSignal:
        print(
            "RuntimeError: 'return' used outside of a function",
            file=stderr,
        )
    except TinylangError as e:
        # Catch-all for anything that slipped past TinyRuntimeError (e.g. a
        # lex/parse error raised mid-evaluation by a nested ``parse`` call).
        print(f"{type(e).__name__}: {e}", file=stderr)


# --------------------------------------------------------------------------- #
# Multi-line detection                                                        #
# --------------------------------------------------------------------------- #


def _needs_more(source: str) -> bool:
    """Return ``True`` if ``source`` has an unbalanced opening bracket.

    The brief says: "a line ending with an opening unbalanced ``{`` / ``(`` /
    ``[`` indicates a multi-line input". We implement a slightly more general
    version: keep reading whenever the cumulative bracket balance is positive,
    regardless of which line that opener was on. This naturally supports
    nested blocks like:

        fn fib(n) {
          if (n < 2) {
            return n;
          }
          return fib(n - 1) + fib(n - 2);
        }

    We do *not* attempt to detect unterminated strings or missing
    semicolons — those produce parse errors that the REPL surfaces normally.
    Strings and ``//`` comments are skipped while counting so that
    ``"hello {"`` and ``// {`` don't trip the matcher.
    """
    depth = 0
    i = 0
    n = len(source)
    while i < n:
        ch = source[i]
        # Skip line comments.
        if ch == "/" and i + 1 < n and source[i + 1] == "/":
            # Consume to end of line.
            while i < n and source[i] != "\n":
                i += 1
            continue
        # Skip string literals.
        if ch == '"':
            i += 1
            while i < n:
                c = source[i]
                if c == "\\" and i + 1 < n:
                    # Skip the escape and its target character.
                    i += 2
                    continue
                if c == '"':
                    i += 1
                    break
                i += 1
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            # Clamp at 0: an *excess* closer is a parse error, not a request
            # for more input. We don't want to wait forever in that case.
            if depth > 0:
                depth -= 1
        i += 1
    return depth > 0


__all__ = ["main"]
