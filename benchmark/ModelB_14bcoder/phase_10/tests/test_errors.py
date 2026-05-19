from tinylang.errors import TinylangError, LexError, ParseError
from tinylang.lexer import tokenize
from tinylang.parser import parse
from tinylang.evaluator import run
import pytest


def _runtime_error_cls():
    """The runtime error class may be named TinyRuntimeError, RuntimeError, or
    similar. We discover it dynamically as the only TinylangError subclass that
    is neither LexError nor ParseError, declared in tinylang.errors."""
    import tinylang.errors as mod
    for name in dir(mod):
        obj = getattr(mod, name)
        if (isinstance(obj, type) and issubclass(obj, TinylangError)
                and obj not in (TinylangError, LexError, ParseError)):
            return obj
    raise AssertionError("no runtime-error subclass declared in tinylang.errors")


def test_lex_error_is_typed():
    with pytest.raises(LexError) as exc:
        tokenize("let x = @;")
    msg = str(exc.value)
    assert exc.value.line == 1
    assert "line" in msg.lower() or "@" in msg


def test_parse_error_is_typed():
    with pytest.raises(ParseError) as exc:
        parse("let x = ;")
    assert exc.value.line == 1
    assert exc.value.col is not None


def test_runtime_error_is_typed_and_has_line():
    RT = _runtime_error_cls()
    with pytest.raises(RT) as exc:
        run("print(missing_var);")
    assert exc.value.line is not None  # parser tracked line/col on Identifier or Call


def test_runtime_error_stack_includes_function_names():
    RT = _runtime_error_cls()
    src = """
fn h() { return missing; }
fn g() { return h(); }
fn f() { return g(); }
f();
"""
    with pytest.raises(RT) as exc:
        run(src)
    stack = getattr(exc.value, "stack", None)
    assert stack is not None and isinstance(stack, list)
    names = [frame.get("fn") for frame in stack]
    assert "f" in names and "g" in names and "h" in names


def test_runtime_error_str_contains_useful_info():
    RT = _runtime_error_cls()
    with pytest.raises(RT) as exc:
        run("print(zz);")
    msg = str(exc.value)
    assert "zz" in msg or "undefined" in msg.lower() or "unknown" in msg.lower()


def test_index_oob_is_runtime_error_typed():
    RT = _runtime_error_cls()
    with pytest.raises(RT):
        run("let xs = [1]; print(xs[10]);")


def test_division_by_zero_is_runtime_error_typed():
    RT = _runtime_error_cls()
    with pytest.raises(RT):
        run("print(1 / 0);")
