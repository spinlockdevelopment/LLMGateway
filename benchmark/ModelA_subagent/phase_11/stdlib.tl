// tinylang standard library — written in tinylang itself.
//
// Loaded automatically by ``tinylang.evaluator.run`` before user source, in
// the same global environment, so every helper below is available as a
// top-level name to user code.
//
// Rules of the road (per phase 11 brief):
//   * Use only features from phases 1-10 (let, if/else, while, for, fn,
//     closures, lists, dicts, recursion, the existing builtins).
//   * Do NOT ``print`` at the top level — the loader strips bootstrap output
//     but we don't want to depend on that. Helpers may of course print if
//     the user explicitly calls them, but the file itself must be quiet
//     when sourced.
//   * No new builtins assumed; everything below is built from ``len``,
//     ``push``, ``keys``/``values``, etc.

// ----------------------------------------------------------------- ranges --
// ``range(a, b)`` — list of numbers from ``a`` (inclusive) up to ``b``
// (exclusive). If ``a >= b`` the result is empty. Step is fixed at +1.
fn range(a, b) {
  let out = [];
  let i = a;
  while (i < b) {
    push(out, i);
    i = i + 1;
  }
  return out;
}

// ``range1(n)`` — shorthand for ``range(0, n)``. Named ``range1`` because
// the language doesn't support optional/variadic params yet, so we can't
// overload ``range`` itself.
fn range1(n) {
  return range(0, n);
}

// --------------------------------------------------------------- higher-order
// ``map(f, xs)`` — new list of ``f(x)`` for each x in xs. Order preserved.
fn map(f, xs) {
  let out = [];
  for (x) in xs {
    push(out, f(x));
  }
  return out;
}

// ``filter(f, xs)`` — new list containing the xs for which ``f(x)`` is truthy.
fn filter(f, xs) {
  let out = [];
  for (x) in xs {
    if (f(x)) {
      push(out, x);
    }
  }
  return out;
}

// ``reduce(f, xs, init)`` — left fold. Walks xs left-to-right, threading the
// accumulator through ``f(acc, x)``. Returns ``init`` for an empty list.
fn reduce(f, xs, init) {
  let acc = init;
  for (x) in xs {
    acc = f(acc, x);
  }
  return acc;
}

// ----------------------------------------------------------------- searching
// ``contains(xs, v)`` — true iff some element of xs equals v. Uses the
// language's ``==`` semantics, so cross-type comparisons just return false
// rather than erroring.
fn contains(xs, v) {
  for (x) in xs {
    if (x == v) {
      return true;
    }
  }
  return false;
}

// ----------------------------------------------------------------- reshaping
// ``reverse(xs)`` — new list with the elements of xs in reverse order. We
// walk the input by index from the back so we don't depend on a built-in
// slice/reverse.
fn reverse(xs) {
  let out = [];
  let n = len(xs);
  let i = n - 1;
  while (i >= 0) {
    push(out, xs[i]);
    i = i - 1;
  }
  return out;
}

// ------------------------------------------------------------------ min/max
// ``min2(a, b)`` / ``max2(a, b)`` — pairwise min/max using ``<``. Works for
// anything ``<`` accepts (numbers and strings, per the brief).
fn min2(a, b) {
  if (a < b) { return a; }
  return b;
}

fn max2(a, b) {
  if (a < b) { return b; }
  return a;
}

// --------------------------------------------------------------------- sum
// ``sum(xs)`` — sum of a list of numbers. Empty list sums to 0.
fn sum(xs) {
  let total = 0;
  for (x) in xs {
    total = total + x;
  }
  return total;
}
