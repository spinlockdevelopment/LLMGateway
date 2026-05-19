from tinylang.evaluator import run


def test_range1_basic():
    assert run("print(range1(5));") == "[0, 1, 2, 3, 4]\n"


def test_range_two_args():
    assert run("print(range(2, 6));") == "[2, 3, 4, 5]\n"


def test_map_double():
    src = """
let xs = range1(4);
let doubled = map(fn(x) { return x * 2; }, xs);
print(doubled);
"""
    assert run(src) == "[0, 2, 4, 6]\n"


def test_filter_evens():
    src = """
let xs = range1(8);
let evens = filter(fn(x) { return x % 2 == 0; }, xs);
print(evens);
"""
    assert run(src) == "[0, 2, 4, 6]\n"


def test_reduce_sum():
    src = """
let xs = range1(5);
print(reduce(fn(acc, x) { return acc + x; }, xs, 0));
"""
    assert run(src) == "10\n"


def test_sum_builtin_in_stdlib():
    assert run("print(sum(range1(5)));") == "10\n"


def test_contains():
    src = """
let xs = [1, 3, 5, 7];
print(contains(xs, 5));
print(contains(xs, 4));
"""
    assert run(src) == "true\nfalse\n"


def test_reverse():
    assert run("print(reverse([1, 2, 3]));") == "[3, 2, 1]\n"


def test_min2_max2():
    assert run("print(min2(3, 7), max2(3, 7));") == "3 7\n"


def test_composing_stdlib():
    # Sum of doubles of even numbers in 0..9: doubles of {0,2,4,6,8} = {0,4,8,12,16}; sum=40
    src = """
let xs = range1(10);
let evens = filter(fn(x) { return x % 2 == 0; }, xs);
let doubled = map(fn(x) { return x * 2; }, evens);
print(sum(doubled));
"""
    assert run(src) == "40\n"
