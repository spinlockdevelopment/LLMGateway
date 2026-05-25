from tinylang.evaluator import run
import traceback

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
    print(f"Result: {run(src)!r}")
except Exception:
    traceback.print_exc()
