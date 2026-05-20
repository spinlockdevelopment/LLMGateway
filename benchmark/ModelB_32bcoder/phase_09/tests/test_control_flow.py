from tinylang.evaluator import evaluate_statements

def run(node: Expression) -> Any:
    env = Environment()
    evaluator = Evaluator(env)
    return evaluator.evaluate(node)


def test_if_true_branch():
    assert run("if (1 < 2) { print(\"yes\"); }") == "yes\n"


def test_if_else():
    src = """
if (1 > 2) { print("a"); } else { print("b"); }
"""
    assert run(src) == "b\n"


def test_else_if_chain():
    src = """
let x = 2;
if (x == 1) { print("one"); }
else if (x == 2) { print("two"); }
else { print("other"); }
"""
    assert run(src) == "two\n"


def test_while_basic():
    src = """
let i = 0;
let sum = 0;
while (i < 5) {
  sum = sum + i;
  i = i + 1;
}
print(sum);
"""
    assert run(src) == "10\n"


def test_break_exits_loop():
    src = """
let i = 0;
while (true) {
  if (i == 3) { break; }
  print(i);
  i = i + 1;
}
"""
    assert run(src) == "0\n1\n2\n"


def test_continue_skips_iteration():
    src = """
let i = 0;
while (i < 5) {
  i = i + 1;
  if (i == 3) { continue; }
  print(i);
}
"""
    assert run(src) == "1\n2\n4\n5\n"


def test_nested_loops_break_only_inner():
    src = """
let i = 0;
while (i < 2) {
  let j = 0;
  while (true) {
    if (j == 2) { break; }
    print(i, j);
    j = j + 1;
  }
  i = i + 1;
}
"""
    assert run(src) == "0 0\n0 1\n1 0\n1 1\n"


def test_truthiness_in_condition():
    src = """
if (0) { print("a"); } else { print("b"); }
if (nil) { print("c"); } else { print("d"); }
if ("") { print("e"); } else { print("f"); }
"""
    # 0 and nil are falsy; "" is truthy (only nil/false/0 are falsy per spec).
    assert run(src) == "b\nd\ne\n"
