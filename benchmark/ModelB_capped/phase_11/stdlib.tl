// Standard library for tinylang

// Create a range of numbers from a to b (exclusive)
fn range(a, b) {
  let result = [];
  let i = a;
  while (i < b) {
    push(result, i);
    i = i + 1;
  }
  return result;
}

// Create a range from 0 to n (exclusive)
fn range1(n) {
  return range(0, n);
}

// Map function: apply f to each element of xs
fn map(f, xs) {
  let result = [];
  for (i, v) in xs {
    push(result, f(v));
  }
  return result;
}

// Filter function: keep elements where f returns truthy
fn filter(f, xs) {
  let result = [];
  for (i, v) in xs {
    if (f(v)) {
      push(result, v);
    }
  }
  return result;
}

// Reduce function: fold left with initial value
fn reduce(f, xs, init) {
  let acc = init;
  for (i, v) in xs {
    acc = f(acc, v);
  }
  return acc;
}

// Check if value is contained in list
fn contains(xs, v) {
  for (i, x) in xs {
    if (x == v) {
      return true;
    }
  }
  return false;
}

// Reverse a list
fn reverse(xs) {
  let result = [];
  let i = len(xs) - 1;
  while (i >= 0) {
    push(result, xs[i]);
    i = i - 1;
  }
  return result;
}

// Minimum of two values
fn min2(a, b) {
  if (a <= b) {
    return a;
  } else {
    return b;
  }
}

// Maximum of two values
fn max2(a, b) {
  if (a >= b) {
    return a;
  } else {
    return b;
  }
}

// Sum of numbers in a list
fn sum(xs) {
  let total = 0;
  for (i, v) in xs {
    total = total + v;
  }
  return total;
}