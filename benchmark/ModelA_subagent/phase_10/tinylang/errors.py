"""Public error hierarchy for tinylang.

Phase 10 replaces the ad-hoc ``raise Exception(...)`` calls used by earlier
phases with a small, structured exception model. Everything user code in the
language can fail with is now a subclass of :class:`TinylangError`, so callers
(tests, the future CLI, embedding programs) can catch the umbrella once and
get every tinylang-level failure.

Hierarchy::

    TinylangError       # umbrella; never raised directly
    ├── LexError        # invalid character / unterminated string / bad escape
    ├── ParseError      # syntactic error (unexpected token, missing ';', ...)
    └── TinyRuntimeError  # everything the evaluator detects at runtime

Each error carries an optional 1-based ``line`` and ``col``. When set, the
default ``__str__`` appends ``" at line L, col C"`` so error messages are
self-describing in a ``pytest`` failure or a CLI ``print``.

Runtime errors additionally carry a call ``stack`` — a list of frame dicts
``{"fn": "<name>", "line": <call-site-line>}`` — populated as the evaluator
unwinds through ``Call`` frames. The convention this module uses is
**innermost first**: ``stack[0]`` is the function that most directly contained
the failing expression, and ``stack[-1]`` is the outermost call site that the
program started from. The :meth:`TinyRuntimeError.traceback` helper renders
the stack as a multi-line string suitable for human display.

Re-export aliases:

* ``ParseError`` keeps its name for parity with the lexer/parser modules.
* The brief mentions ``RuntimeError as TinyRuntimeError``; we expose the class
  under both names — ``TinyRuntimeError`` is the canonical one and
  ``RuntimeError`` is available as an alias *inside* this module (not
  re-exported into Python builtins) so callers can do
  ``from tinylang.errors import RuntimeError as TinyRuntimeError``.
"""

from __future__ import annotations

from typing import Any, List, Optional


class TinylangError(Exception):
    """Umbrella class for every tinylang-level error.

    Parameters
    ----------
    message:
        Human-readable description of what went wrong.
    line, col:
        Optional 1-based source coordinates. Either may be ``None`` when the
        error has no useful location (for example, a ``break`` that bubbles
        past every loop).

    Attributes
    ----------
    message, line, col:
        As passed to ``__init__``.
    """

    message: str
    line: Optional[int]
    col: Optional[int]

    def __init__(
        self,
        message: str,
        line: Optional[int] = None,
        col: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.line = line
        self.col = col

    def __str__(self) -> str:
        if self.line is not None and self.col is not None:
            return f"{self.message} at line {self.line}, col {self.col}"
        if self.line is not None:
            return f"{self.message} at line {self.line}"
        return self.message


class LexError(TinylangError):
    """Raised by :func:`tinylang.lexer.tokenize` on invalid input."""


class ParseError(TinylangError):
    """Raised by :func:`tinylang.parser.parse` on a syntactic error."""


class TinyRuntimeError(TinylangError):
    """Raised by the evaluator for any tinylang-level runtime failure.

    In addition to the base ``message``/``line``/``col``, this class records a
    call stack populated as the error unwinds through user-defined function
    calls. ``stack`` is **innermost first**: ``stack[0]`` is the function the
    failure happened in, ``stack[-1]`` is the outermost call site.

    Use :meth:`traceback` to render a multi-line, human-readable view of the
    error and its call chain.
    """

    stack: List[dict]

    def __init__(
        self,
        message: str,
        line: Optional[int] = None,
        col: Optional[int] = None,
        stack: Optional[List[dict]] = None,
    ) -> None:
        super().__init__(message, line=line, col=col)
        # Defensive copy so callers can't mutate the list we hold.
        self.stack = list(stack) if stack else []

    def push_frame(self, fn: str, line: Optional[int]) -> None:
        """Record a new call-site frame as the exception unwinds.

        The evaluator calls this from its ``Call`` handler so the innermost
        frame is appended first and the outermost last; that matches the
        ``stack[0] == innermost`` convention.
        """
        self.stack.append({"fn": fn, "line": line})

    def traceback(self) -> str:
        """Return a multi-line string describing the error + its call stack.

        The format is intentionally simple so it can be pasted straight into
        a CLI message:

        ::

            RuntimeError: undefined variable 'foo' at line 7, col 3
              in <anonymous> at line 5
              in main at line 1
        """
        head = f"RuntimeError: {self}"
        if not self.stack:
            return head
        lines = [head]
        for frame in self.stack:
            fn = frame.get("fn", "<unknown>")
            ln = frame.get("line")
            if ln is None:
                lines.append(f"  in {fn}")
            else:
                lines.append(f"  in {fn} at line {ln}")
        return "\n".join(lines)


# Alias so callers may write ``from tinylang.errors import RuntimeError``
# without shadowing Python's built-in in their own namespace.
RuntimeError = TinyRuntimeError


__all__ = [
    "TinylangError",
    "LexError",
    "ParseError",
    "TinyRuntimeError",
    "RuntimeError",
]
