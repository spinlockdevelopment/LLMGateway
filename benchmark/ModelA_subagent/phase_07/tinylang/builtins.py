"""Built-in functions for tinylang.

Phase 3 only requires ``print``. Later phases will extend this module with
``len``, ``push``, ``pop``, ``keys``, ``values``, ``has``, ``del``, ``str``,
``num`` and ``range``.

Each built-in is invoked by the evaluator with the program's output buffer
threaded through via the :func:`make_builtins` factory so that ``print`` can
write into the captured ``run`` output.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List


def format_value(value: Any) -> str:
    """Return tinylang's display form for ``value``.

    - Numbers with no fractional part render without ``.0`` (``5``, not ``5.0``).
    - Other numbers use Python's default ``repr`` (shortest round-trippable).
    - Booleans render as ``true``/``false`` (lowercase).
    - ``nil`` renders as ``nil``.
    - Strings render without quotes.
    - Lists / dicts render with their tinylang-style brackets and recursively
      formatted members (handy for later phases; harmless here).
    """

    # Order matters: ``bool`` is a subclass of ``int`` in Python, so check it
    # before numeric handling.
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if value != value:  # NaN
            return "nan"
        if value == float("inf"):
            return "inf"
        if value == float("-inf"):
            return "-inf"
        if value.is_integer():
            # Avoid scientific notation for big-but-integer floats.
            return str(int(value))
        return repr(value)
    if isinstance(value, int):  # not expected, but be lenient
        return str(value)
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "[" + ", ".join(format_value(v) for v in value) + "]"
    if isinstance(value, dict):
        parts = []
        for k, v in value.items():
            parts.append(f"{format_value(k)}: {format_value(v)}")
        return "{" + ", ".join(parts) + "}"
    # Functions and other opaque values: fall back to ``repr``.
    return repr(value)


def make_builtins(output: List[str]) -> Dict[str, Callable[..., Any]]:
    """Build the built-in environment, wiring ``print`` into ``output``."""

    def _print(*args: Any) -> None:
        output.append(" ".join(format_value(a) for a in args) + "\n")
        return None

    return {
        "print": _print,
    }
