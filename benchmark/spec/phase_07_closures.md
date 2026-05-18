# Phase 7 — Closures

Read `spec/overall_brief.md` first.

## Goal

Make sure inner functions properly capture and **share** their enclosing
environment by reference. After this phase, the classic counter pattern works.

## Scope

This phase is mostly a correctness pass on phase 6. There is typically no new
AST or new public surface; you are verifying that:

- A function literal captures the env in which it was **defined**, not the env
  in which it is **called**.
- Multiple closures sharing the same enclosing scope mutate the **same**
  bindings.
- A closure can outlive the function call that produced it (the captured env
  is held by the `Function` value and survives the outer call returning).

If your phase 6 implementation already did this correctly, the change here may
be small (or zero, plus the new tests). Reviewers will still look at the code
to confirm the env model is sound.

## Required behaviors

```tinylang
let make_counter = fn() {
  let n = 0;
  return fn() { n = n + 1; return n; };
};
let c = make_counter();
print(c());   // 1
print(c());   // 2
print(c());   // 3

let make_adder = fn(x) {
  return fn(y) { return x + y; };
};
let add5 = make_adder(5);
print(add5(10));   // 15
print(add5(20));   // 25

// Two closures sharing state:
fn pair() {
  let n = 0;
  let inc = fn() { n = n + 1; return n; };
  let get = fn() { return n; };
  return [inc, get];     // lists exist in phase 8; for this phase, use a dict-of-fns or two return values via separate calls. The tests use phase-appropriate constructs.
}
```

The pair() example above uses lists which arrive in phase 8 — the actual test
file for phase 7 uses only constructs already available (numbers, booleans,
strings, functions). Don't worry about the multiple-return-value problem; the
tests stick to single closures and counters.

## Out of scope

- New built-ins.
- Lists, dicts. Closures over later data types come for free once those land.
