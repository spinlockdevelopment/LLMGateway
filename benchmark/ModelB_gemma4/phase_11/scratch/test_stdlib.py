from tinylang.evaluator import run

src = """
let xs = range1(5);
let doubled = map(fn(x) { return x * 2; }, xs);
let evens = filter(fn(x) { return x % 2 == 0; }, doubled);
print(sum(evens));            // 0+2+4+6+8 doubled, evens = all of them, sum = 20
print(contains(doubled, 6));  // true
"""

print("Result:")
print(run(src))
