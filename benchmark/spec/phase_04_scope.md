# Phase 4 — Variables, assignment, blocks, lexical scope

Read `spec/overall_brief.md` first.

## Goal

Add variable definition (`let`), reassignment (`=`), block scope (`{ ... }`)
with proper lexical lookup, and shadowing.

## Scope

- Produce `tinylang/environment.py` with an `Environment` class (or equivalent).
  Each environment has a parent and a local dict.
- Extend `tinylang/evaluator.py` so `run(source)` handles `LetStmt`, `Block`,
  identifier references, and `Assign` (the AST node, where target is an
  `Identifier`).
- Looking up an unknown name → runtime error with the name and approx
  location.
- `let x = ...` introduces `x` in the **current** environment, shadowing outer
  bindings.
- `x = ...` (without `let`) assigns to the nearest enclosing binding of `x`.
  Assigning to a name that is not in scope is a runtime error (you may not
  silently create a global).
- A block opens a fresh child environment. Variables declared inside it are
  not visible outside. Variables declared outside remain visible inside.
- Re-declaring the same name in the **same** scope (two `let x` at the same
  level) is a runtime error. (Re-declaring in a child block is shadowing —
  that is fine.)

## Public surface unchanged

`run(source: str) -> str` continues to be the entry point. Same return-value
contract as phase 3.

## Examples

```tinylang
let x = 1;
let y = x + 1;
print(x, y);       // 1 2

{
  let x = 99;
  print(x);        // 99
}
print(x);          // 1 (outer x unaffected)

x = 5;
print(x);          // 5

z = 1;             // runtime error: undefined "z"
```

## Out of scope

- Control flow — phase 5.
- Functions and their parameter binding — phase 6, though parameter binding
  will use the same `Environment` you build here, so design it to be reusable.
- Assignment to `Index` targets (`xs[0] = 1`, `d["k"] = 1`) — those land in
  phases 8 and 9 respectively.
