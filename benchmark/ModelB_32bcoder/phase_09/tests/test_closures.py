from tinylang.evaluator import evaluate_statements

def run(node: Expression) -> Any:
    env = Environment()
    evaluator = Evaluator(env)
    return evaluator.evaluate(node)


def test_counter_closure_remembers_state():
    src = """
let make_counter = fn() {
  let n = 0;
  return fn() { n = n + 1; return n; };
};
let c = make_counter();
print(c());
print(c());
print(c());
"""
    assert run(src) == "1\n2\n3\n"


def test_two_counters_have_independent_state():
    src = """
let make_counter = fn() {
  let n = 0;
  return fn() { n = n + 1; return n; };
};
let a = make_counter();
let b = make_counter();
print(a());
print(a());
print(b());
print(a());
print(b());
"""
    assert run(src) == "1\n2\n1\n3\n2\n"


def test_make_adder():
    src = """
let make_adder = fn(x) {
  return fn(y) { return x + y; };
};
let add5 = make_adder(5);
let add10 = make_adder(10);
print(add5(3));
print(add10(3));
print(add5(100));
"""
    assert run(src) == "8\n13\n105\n"


def test_closure_captures_by_reference_not_value():
    src = """
let x = 1;
let get_x = fn() { return x; };
x = 99;
print(get_x());
"""
    assert run(src) == "99\n"


def test_inner_function_uses_outer_param_after_outer_returned():
    # Outer scope must persist via closure even after outer returns.
    src = """
let outer = fn(msg) {
  return fn() { return msg + "!"; };
};
let f = outer("hi");
print(f());
print(f());
"""
    assert run(src) == "hi!\nhi!\n"


def test_recursive_closure_via_let_then_assign():
    # Demonstrates the closure captures the binding, so reassignment is visible.
    src = """
let f = nil;
f = fn(n) {
  if (n <= 0) { return 0; }
  return n + f(n - 1);
};
print(f(5));
"""
    assert run(src) == "15\n"
