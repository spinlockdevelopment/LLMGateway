# Phase 11 — Standard library written in tinylang

Read `spec/overall_brief.md` first.

## Goal

Bootstrap a small standard library **written in tinylang itself**, loaded
automatically before user code runs. This phase tests that your language is
expressive enough to write real code in.

## Scope

- Produce `stdlib.tl` at the workdir root (next to the `tinylang/` package).
- Modify `tinylang/evaluator.py` (and / or a small loader module) so that
  `run(source)` first parses and executes `stdlib.tl`, **then** evaluates the
  user source, in the **same** global environment. The stdlib defines its
  helpers as top-level functions in the global env, so user code can call them
  directly.
- The bootstrap step must not have its `print` output leak into the test
  output — only output from the user source is included in the return value
  of `run`. (Easiest implementation: `stdlib.tl` does not call `print` at the
  top level.)
- If `stdlib.tl` is missing, `run` still works — fall back to no stdlib. This
  matters because tests for phases 1–10 do not ship a `stdlib.tl`.

## Functions to implement in tinylang

In `stdlib.tl`, define at least these:

| name                    | meaning                                                 |
|-------------------------|---------------------------------------------------------|
| `range(a, b)`           | list of numbers `a, a+1, ..., b-1`                      |
| `range1(n)`             | same as `range(0, n)`                                   |
| `map(f, xs)`            | list of `f(x)` for x in xs                              |
| `filter(f, xs)`         | list of x in xs where `f(x)` is truthy                  |
| `reduce(f, xs, init)`   | left fold, returns final accumulator                    |
| `contains(xs, v)`       | true iff some element of xs equals v                    |
| `reverse(xs)`           | reversed list                                           |
| `min2(a, b)`            | smaller of two values (using `<`)                       |
| `max2(a, b)`            | larger of two                                           |
| `sum(xs)`               | sum of numbers in xs                                    |

Implement each using only language features from phases 1–10 (recursion or
`while`/`for` are both fine). They must work for typical inputs.

## Example user program

```tinylang
let xs = range1(5);
let doubled = map(fn(x) { return x * 2; }, xs);
let evens = filter(fn(x) { return x % 2 == 0; }, doubled);
print(sum(evens));            // 0+2+4+6+8 doubled, evens = all of them, sum = 20
print(contains(doubled, 6));  // true
```

## Loader implementation hints

- Add a module-level constant or function `STDLIB_PATH` in evaluator.py
  pointing to `Path(__file__).parent.parent / "stdlib.tl"` — or pass a path
  through the loader. Make this overridable so tests can supply a different
  path if needed.
- Catch `FileNotFoundError` and proceed without stdlib.

## Out of scope

- File I/O from tinylang code. Stdlib doesn't read files.
- Module / import system inside tinylang. Everything is global.
