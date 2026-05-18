# Phase 6 — Functions

Read `spec/overall_brief.md` first.

## Goal

Add function declarations, function literals, calls, parameter binding, and
`return`.

## Scope

- Define a `Function` value type (a class in `evaluator.py` or a new module).
  It stores: parameter name list, body block AST, and the **defining
  environment**.
- Handle the AST nodes `FnDecl`, `FnLit`, `Call`, `ReturnStmt`.
- `FnDecl` binds the function in the **current** environment (as if by `let`).
- A `Call` evaluates the callee, then the args (left to right), then creates a
  fresh child env whose parent is the function's defining environment (NOT the
  caller's environment — this matters for closures in phase 7). Parameters
  bind into that child env, the body executes, the call returns the value
  passed to `return`, or `nil` if the function fell off the end.
- Arity mismatch (caller passed too many / too few args) → runtime error.
- Calling a non-function value (e.g. `(1)()`) → runtime error.
- Built-in functions (`print` and any future ones) appear as callable values
  in the global environment. They can live as Python callables or a wrapper
  class — your choice — but `Call` must dispatch to them.

## Examples

```tinylang
fn add(a, b) { return a + b; }
print(add(2, 3));    // 5

fn fact(n) {
  if (n <= 1) { return 1; }
  return n * fact(n - 1);
}
print(fact(5));      // 120

let inc = fn(x) { return x + 1; };
print(inc(10));      // 11

let apply = fn(f, x) { return f(x); };
print(apply(inc, 4));  // 5
```

## Out of scope

- Closures over captured **mutable** state — phase 7. (Calling a
  function-defined-inside-a-function will work here, but the specific
  counter-pattern tests live in phase 7.)
- Lists, dicts, errors with stack traces, etc.

## Note

Make sure recursion via `fn name(...)` works: when `name` is referenced
inside the body, lookup walks up to the env where it was declared. This is
why `FnDecl` must bind `name` **before** the function body is allowed to
reference itself.
