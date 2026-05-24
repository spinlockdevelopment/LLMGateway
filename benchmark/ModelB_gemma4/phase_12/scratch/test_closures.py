from tinylang.evaluator import run

def test_shared_state():
    source = """
let n = 0;
let inc = fn() { n = n + 1; return n; };
let get = fn() { return n; };
print(inc());
print(get());
print(inc());
print(get());
"""
    res = run(source)
    print(f"Shared state test: {res!r}")
    assert res == "1\n1\n2\n2\n"

def test_counter():
    source = """
let make_counter = fn() {
  let n = 0;
  return fn() { n = n + 1; return n; };
};
let c = make_counter();
print(c());
print(c());
print(c());
"""
    res = run(source)
    print(f"Counter test: {res!r}")
    assert res == "1\n2\n3\n"

def test_adder():
    source = """
let make_adder = fn(x) {
  return fn(y) { return x + y; };
};
let add5 = make_adder(5);
print(add5(10));
print(add5(20));
"""
    res = run(source)
    print(f"Adder test: {res!r}")
    assert res == "15\n25\n"

if __name__ == "__main__":
    test_shared_state()
    test_counter()
    test_adder()
    print("All tests passed!")
