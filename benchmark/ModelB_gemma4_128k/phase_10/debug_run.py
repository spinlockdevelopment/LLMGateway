from tinylang.evaluator import run

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
try:
    result = run(src)
    print(f"Result: {repr(result)}")
except Exception as e:
    print(f"Exception: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
