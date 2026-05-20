from tinylang.evaluator import Evaluator

def run(node: Expression) -> Any:
    env = Environment()
    evaluator = Evaluator(env)
    return evaluator.evaluate(node)
import pytest


def test_fn_decl_and_call():
    src = """
fn add(a, b) { return a + b; }
print(add(2, 3));
"""
    assert run(src) == "5\n"


def test_fn_lit_assigned_and_called():
    src = """
let inc = fn(x) { return x + 1; };
print(inc(10));
"""
    assert run(src) == "11\n"


def test_return_nil_when_falls_off_end():
    src = """
fn noop() { let _x = 1; }
print(noop());
"""
    assert run(src) == "nil\n"


def test_recursion_factorial():
    src = """
fn fact(n) {
  if (n <= 1) { return 1; }
  return n * fact(n - 1);
}
print(fact(5));
"""
    assert run(src) == "120\n"


def test_first_class_function_as_argument():
    src = """
fn apply(f, x) { return f(x); }
let dbl = fn(x) { return x * 2; };
print(apply(dbl, 7));
"""
    assert run(src) == "14\n"


def test_arity_error_too_few():
    with pytest.raises(Exception):
        run("fn f(a, b) { return a; } f(1);")


def test_arity_error_too_many():
    with pytest.raises(Exception):
        run("fn f(a) { return a; } f(1, 2);")


def test_call_non_function_errors():
    with pytest.raises(Exception):
        run("let x = 5; x();")


def test_return_early_exits_fn_not_program():
    src = """
fn f(x) {
  if (x > 0) { return "pos"; }
  return "zero_or_neg";
}
print(f(1));
print(f(0));
print("after");
"""
    assert run(src) == "pos\nzero_or_neg\nafter\n"


def test_recursion_fibonacci():
    src = """
fn fib(n) {
  if (n < 2) { return n; }
  return fib(n - 1) + fib(n - 2);
}
print(fib(10));
"""
    assert run(src) == "55\n"
