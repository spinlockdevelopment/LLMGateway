fn range(a, b) {
  let res = [];
  let i = a;
  while (i < b) {
    push(res, i);
    i = i + 1;
  }
  return res;
}

fn range1(n) {
  return range(0, n);
}

fn map(f, xs) {
  let res = [];
  for (x) in xs {
    push(res, f(x));
  }
  return res;
}

fn filter(f, xs) {
  let res = [];
  for (x) in xs {
    if (f(x)) {
      push(res, x);
    }
  }
  return res;
}

fn reduce(f, xs, init) {
  let acc = init;
  for (x) in xs {
    acc = f(acc, x);
  }
  return acc;
}

fn contains(xs, v) {
  for (x) in xs {
    if (x == v) {
      return true;
    }
  }
  return false;
}

fn reverse(xs) {
  let res = [];
  let n = len(xs);
  let i = n - 1;
  while (i >= 0) {
    push(res, xs[i]);
    i = i - 1;
  }
  return res;
}

fn min2(a, b) {
  if (a < b) {
    return a;
  }
  return b;
}

fn max2(a, b) {
  if (a > b) {
    return a;
  }
  return b;
}

fn sum(xs) {
  let s = 0;
  for (x) in xs {
    s = s + x;
  }
  return s;
}
