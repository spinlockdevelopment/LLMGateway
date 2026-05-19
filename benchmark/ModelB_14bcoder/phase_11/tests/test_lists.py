from tinylang.evaluator import run
import pytest


def test_list_literal_and_print():
    assert run("print([1, 2, 3]);") == "[1, 2, 3]\n"


def test_empty_list():
    assert run("print([]);") == "[]\n"


def test_index_read():
    assert run("let xs = [10, 20, 30]; print(xs[0], xs[1], xs[2]);") == "10 20 30\n"


def test_index_out_of_bounds_errors():
    with pytest.raises(Exception):
        run("let xs = [1]; print(xs[5]);")


def test_index_write():
    src = """
let xs = [1, 2, 3];
xs[1] = 99;
print(xs);
"""
    assert run(src) == "[1, 99, 3]\n"


def test_len_of_list():
    assert run("print(len([1, 2, 3, 4]));") == "4\n"
    assert run("print(len([]));") == "0\n"


def test_push_appends_and_mutates():
    src = """
let xs = [1, 2];
push(xs, 3);
print(xs);
print(len(xs));
"""
    assert run(src) == "[1, 2, 3]\n3\n"


def test_pop_returns_and_shrinks():
    src = """
let xs = [10, 20, 30];
let last = pop(xs);
print(last);
print(xs);
"""
    assert run(src) == "30\n[10, 20]\n"


def test_pop_empty_errors():
    with pytest.raises(Exception):
        run("pop([]);")


def test_nested_lists():
    src = """
let m = [[1, 2], [3, 4]];
print(m[0][1]);
print(m[1][0]);
"""
    assert run(src) == "2\n3\n"


def test_list_passed_to_fn_mutates_caller_view():
    src = """
fn add_one(xs) { push(xs, 1); }
let xs = [];
add_one(xs);
add_one(xs);
print(xs);
"""
    assert run(src) == "[1, 1]\n"
