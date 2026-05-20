from tinylang.evaluator import evaluate_statements

def run(node: Expression) -> Any:
    env = Environment()
    evaluator = Evaluator(env)
    return evaluator.evaluate(node)
import pytest


def test_print_integer_no_decimal():
    assert run("print(5);") == "5\n"


def test_arithmetic_precedence():
    assert run("print(1 + 2 * 3);") == "7\n"
    assert run("print((1 + 2) * 3);") == "9\n"


def test_subtraction_and_unary_minus():
    assert run("print(10 - 3);") == "7\n"
    assert run("print(-5 + 7);") == "2\n"


def test_float_division():
    assert run("print(3 / 2);") == "1.5\n"


def test_modulo():
    assert run("print(7 % 3);") == "1\n"


def test_divide_by_zero():
    with pytest.raises(Exception):
        run("print(1 / 0);")


def test_string_concat():
    assert run('print("hi" + " " + "you");') == "hi you\n"


def test_compare_numbers():
    assert run("print(1 < 2, 2 < 1);") == "true false\n"


def test_compare_equal_unlike_types_is_false():
    assert run('print(1 == "1");') == "false\n"


def test_logical_short_circuit_returns_operand():
    # && returns the falsy operand or the last truthy; || returns the first truthy.
    assert run('print(true && "x");') == "x\n"
    assert run('print(false || "y");') == "y\n"
    assert run('print(0 || "z");') == "z\n"


def test_negation_returns_bool():
    assert run("print(!true, !false, !0, !1);") == "false true true false\n"


def test_nil_prints_as_nil():
    assert run("print(nil);") == "nil\n"


def test_bool_prints_as_lowercase():
    assert run("print(true, false);") == "true false\n"


def test_string_plus_number_errors():
    with pytest.raises(Exception):
        run('print("a" + 1);')


def test_compare_string_and_number_errors():
    with pytest.raises(Exception):
        run('print("a" < 1);')
