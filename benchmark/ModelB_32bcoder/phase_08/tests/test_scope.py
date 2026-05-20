from tinylang.evaluator import Evaluator

def run(node: Expression) -> Any:
    env = Environment()
    evaluator = Evaluator(env)
    return evaluator.evaluate(node)
import pytest


def test_let_and_use():
    assert run("let x = 5; print(x);") == "5\n"
    assert run("let x = 1; let y = x + 1; print(y);") == "2\n"


def test_shadowing_inside_block_does_not_affect_outer():
    src = """
let x = 1;
{
  let x = 99;
  print(x);
}
print(x);
"""
    assert run(src) == "99\n1\n"


def test_block_local_not_visible_outside():
    src = """
{
  let only_inside = 7;
  print(only_inside);
}
"""
    assert run(src) == "7\n"
    with pytest.raises(Exception):
        run("{ let z = 1; } print(z);")


def test_assign_to_outer_binding():
    src = """
let x = 1;
{
  x = x + 10;
}
print(x);
"""
    assert run(src) == "11\n"


def test_undefined_variable_errors():
    with pytest.raises(Exception):
        run("print(undefined_var);")


def test_assign_to_undefined_errors():
    with pytest.raises(Exception):
        run("z = 1;")


def test_redeclare_in_same_scope_errors():
    with pytest.raises(Exception):
        run("let x = 1; let x = 2;")


def test_nested_blocks_chain_lookup():
    src = """
let a = 1;
{
  let b = 2;
  {
    let c = 3;
    print(a, b, c);
  }
}
"""
    assert run(src) == "1 2 3\n"
