# Phase 9 — Dicts and `for ... in ...`

Read `spec/overall_brief.md` first.

## Goal

Add dict values, dict literals, indexing, dict-related built-ins, and the
`for` statement that iterates lists and dicts.

## Scope

- Evaluate `DictLit` → Python `dict`. Keys may be strings or numbers; values
  any tinylang value.
- `d[k]` reads. Missing key → runtime error.
- `d[k] = v` writes (inserts if missing).
- Built-ins (add to `tinylang/builtins.py`):
  - `keys(d)` → list of keys in insertion order.
  - `values(d)` → list of values in insertion order.
  - `has(d, k)` → bool.
  - `del(d, k)` → remove key; missing key is a runtime error; returns `nil`.
- `for` statement (AST node `ForStmt`):
  - `for (x) in xs { ... }` — `xs` is a list; bind `x` to each element.
  - `for (i, x) in xs { ... }` — when `xs` is a list, bind `i` to the 0-based
    index and `x` to the element.
  - `for (k, v) in d { ... }` — `d` is a dict; bind `k` and `v` to each pair.
  - Each iteration is a fresh child scope. `break` and `continue` work as in
    `while`. Modifying the iterable during iteration is undefined behavior —
    you do not need to detect this.
- `print` of a dict: `{"a": 1, "b": 2}` style, keys in insertion order. String
  keys are quoted; numeric keys are unquoted.

## Examples

```tinylang
let d = {"a": 1, "b": 2};
print(d["a"]);          // 1
d["c"] = 3;
print(keys(d));         // ["a", "b", "c"]
print(values(d));       // [1, 2, 3]
print(has(d, "a"), has(d, "z"));   // true false
del(d, "b");
print(d);               // {"a": 1, "c": 3}

let xs = [10, 20, 30];
for (x) in xs { print(x); }                // 10 20 30
for (i, x) in xs { print(i, x); }          // 0 10 / 1 20 / 2 30
for (k, v) in d { print(k, v); }           // a 1 / c 3
```

## Out of scope

- Set type, ordered maps, custom equality.
- Stdlib helpers like `map`/`filter` — phase 11.
