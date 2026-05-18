# Phase 8 — Lists

Read `spec/overall_brief.md` first.

## Goal

Add list values, list literals, indexing (read and write), and three
list-related built-ins.

## Scope

- Evaluate `ListLit` to a Python `list` of evaluated items.
- Evaluate `Index` for lists: `xs[i]` reads the i'th element. `i` must be a
  number with no fractional part (else error). Negative or out-of-range
  indices → runtime error.
- Evaluate `Assign` whose target is `Index`: `xs[i] = v` writes in place.
  Out-of-range indices on assignment → runtime error (no auto-growth).
- Built-ins (add to `tinylang/builtins.py`):
  - `len(x)` — on a list, returns its length. (Also already works on strings;
    you may keep that here or save it for stdlib.)
  - `push(xs, v)` — appends `v` to `xs`, mutates in place, returns `nil`.
  - `pop(xs)` — removes and returns the last element. Empty list → runtime
    error.
- `print` of a list: `[1, 2, 3]` style. Nested lists print nested.

## Examples

```tinylang
let xs = [1, 2, 3];
print(xs);           // [1, 2, 3]
print(xs[0]);        // 1
print(len(xs));      // 3
push(xs, 4);
print(xs);           // [1, 2, 3, 4]
xs[1] = 20;
print(xs);           // [1, 20, 3, 4]
let last = pop(xs);
print(last, xs);     // 3 [1, 20, 3]      // note: last popped was the trailing 4? Re-read: after the previous line, pop returns 4. The expected output should be: 4 [1, 20, 3]
```

(Yes — `pop` on `[1, 20, 3, 4]` returns `4`. The comment above is illustrative
of what the model should print; tests are the source of truth.)

## Out of scope

- Slicing.
- Comprehensions.
- `map`, `filter`, `reduce`, `range` — those land in phase 11 as tinylang
  stdlib code.
- Dicts.
