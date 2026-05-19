// Standard library for tinylang

fn range(a, b) {
  let result = [];
  let i = a;
  while (i < b) {
    push(result, i);
    i = i + 1;
  }
  return result;
}

fn range1(n) {
  return range(0, n);
}

fn map(f, xs) {
  let result = [];
  for (x in xs) {
    push(result, f(x));
  }
  return result;
}

fn filter(f, xs) {
  let result = [];
  for (x in xs) {
    if (f(x)) {
      push(result, x);
    }
  }
  return result;
}

fn reduce(f, xs, init) {
  let acc = init;
  for (x in xs) {
    acc = f(acc, x);
  }
  return acc;
}

fn contains(xs, v) {
  for (x in xs) {
    if (x == v) {
      return true;
    }
  }
  return false;
}

fn reverse(xs) {
  let result = [];
  let i = len(xs) - 1;
  while (i >= 0) {
    push(result, xs[i]);
    i = i - 1;
  }
  return result;
}

fn min2(a, b) {
  if (a < b) {
    return a;
  } else {
    return b;
  }
}

fn max2(a, b) {
  if (a > b) {
    return a;
  } else {
    return b;
  }
}

fn sum(xs) {
  return reduce(fn(acc, x) { return acc + x; }, xs, 0);
}