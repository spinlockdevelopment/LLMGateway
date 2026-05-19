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


def _len(x: Any) -> float:
    """``len(x)`` — length of a string or list (phase 8).

    Returns a float so it composes with tinylang's number type. Other types
    (number, bool, nil, function) raise a runtime error.
    """
    if isinstance(x, bool):
        # ``bool`` is a subclass of ``int``; reject it explicitly so
        # ``len(true)`` doesn't accidentally succeed.
        raise Exception("len() requires a string or list, got bool")
    if isinstance(x, (str, list)):
        return float(len(x))
    if isinstance(x, dict):
        # Dicts land in phase 9; surface a clear message here.
        raise Exception("len() requires a string or list, got dict")
    if x is None:
        raise Exception("len() requires a string or list, got nil")
    if isinstance(x, float):
        raise Exception("len() requires a string or list, got number")
    raise Exception(f"len() requires a string or list, got {type(x).__name__}")


def _push(xs: Any, value: Any) -> None:
    """``push(xs, v)`` — append v to xs (mutates), returns nil."""
    if not isinstance(xs, list):
        raise Exception(
            f"push() requires a list as first argument, got {_value_kind(xs)}"
        )
    xs.append(value)
    return None


def _pop(xs: Any) -> Any:
    """``pop(xs)`` — remove and return the last element. Empty → error."""
    if not isinstance(xs, list):
        raise Exception(
            f"pop() requires a list, got {_value_kind(xs)}"
        )
    if not xs:
        raise Exception("pop() on empty list")
    return xs.pop()


def _value_kind(value: Any) -> str:
    """Short type name for error messages — mirrors evaluator._type_name."""
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, float) or isinstance(value, int):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    if callable(value):
        return "function"
    return type(value).__name__


def make_builtins(output: List[str]) -> Dict[str, Callable[..., Any]]:
    """Build the built-in environment, wiring ``print`` into ``output``."""

    def _print(*args: Any) -> None:
        output.append(" ".join(format_value(a) for a in args) + "\n")
        return None

    return {
        "print": _print,
        "len": _len,
        "push": _push,
        "pop": _pop,
    }
