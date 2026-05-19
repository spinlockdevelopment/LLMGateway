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
        return "[" + ", ".join(_format_element(v) for v in value) + "]"
    if isinstance(value, dict):
        parts = []
        for k, v in value.items():
            parts.append(f"{_format_dict_key(k)}: {_format_element(v)}")
        return "{" + ", ".join(parts) + "}"
    # Functions and other opaque values: fall back to ``repr``.
    return repr(value)


def _format_element(value: Any) -> str:
    """Render ``value`` as it should appear *inside* a list or dict.

    Differs from :func:`format_value` only for strings, which are quoted
    (with double quotes and the standard escapes) so that printed
    containers round-trip through the tinylang lexer.
    """
    if isinstance(value, str):
        return _quote_string(value)
    return format_value(value)


def _format_dict_key(key: Any) -> str:
    """Render a dict key for display.

    Per the phase 9 spec: string keys are quoted, numeric keys unquoted.
    Other key types fall back to their normal display form.
    """
    if isinstance(key, str):
        return _quote_string(key)
    return format_value(key)


def _quote_string(s: str) -> str:
    """Double-quote ``s`` using the same escapes the lexer accepts."""
    out = ['"']
    for ch in s:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _len(x: Any) -> float:
    """``len(x)`` — length of a string, list, or dict.

    Returns a float so it composes with tinylang's number type. Other types
    (number, bool, nil, function) raise a runtime error.
    """
    if isinstance(x, bool):
        # ``bool`` is a subclass of ``int``; reject it explicitly so
        # ``len(true)`` doesn't accidentally succeed.
        raise Exception("len() requires a string, list, or dict, got bool")
    if isinstance(x, (str, list, dict)):
        return float(len(x))
    if x is None:
        raise Exception("len() requires a string, list, or dict, got nil")
    if isinstance(x, float):
        raise Exception("len() requires a string, list, or dict, got number")
    raise Exception(
        f"len() requires a string, list, or dict, got {type(x).__name__}"
    )


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


def _require_dict(name: str, d: Any) -> dict:
    if not isinstance(d, dict):
        raise Exception(
            f"{name}() requires a dict, got {_value_kind(d)}"
        )
    return d


def _keys(d: Any) -> list:
    """``keys(d)`` — list of dict keys in insertion order."""
    return list(_require_dict("keys", d).keys())


def _values(d: Any) -> list:
    """``values(d)`` — list of dict values in insertion order."""
    return list(_require_dict("values", d).values())


def _has(d: Any, key: Any) -> bool:
    """``has(d, k)`` — True if ``d`` contains key ``k``."""
    return key in _require_dict("has", d)


def _del(d: Any, key: Any) -> None:
    """``del(d, k)`` — remove ``k`` from ``d``; missing key is an error."""
    target = _require_dict("del", d)
    if key not in target:
        raise Exception(f"del(): missing key {_format_key_for_error(key)}")
    del target[key]
    return None


def _format_key_for_error(key: Any) -> str:
    if isinstance(key, str):
        return repr(key)
    return format_value(key)


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
        "keys": _keys,
        "values": _values,
        "has": _has,
        "del": _del,
    }
