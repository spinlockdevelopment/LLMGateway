from tinylang.evaluator import evaluate_statements
import pytest


def test_dict_literal_and_index():
    src = """
let d = {"a": 1, "b": 2};
print(d["a"]);
print(d["b"]);
"""
    assert run(src) == "1\n2\n"


def test_missing_key_errors():
    with pytest.raises(Exception):
        run('let d = {"a": 1}; print(d["z"]);')


def test_set_new_key():
    src = """
let d = {};
d["x"] = 10;
print(d["x"]);
"""
    assert run(src) == "10\n"


def test_keys_values_has_del():
    src = """
let d = {"a": 1, "b": 2, "c": 3};
print(keys(d));
print(values(d));
print(has(d, "a"));
print(has(d, "z"));
del(d, "b");
print(keys(d));
"""
    expected = (
        '["a", "b", "c"]\n'
        "[1, 2, 3]\n"
        "true\n"
        "false\n"
        '["a", "c"]\n'
    )
    assert run(src) == expected


def test_for_over_list_one_var():
    src = """
let xs = [10, 20, 30];
for (x) in xs { print(x); }
"""
    assert run(src) == "10\n20\n30\n"


def test_for_over_list_enumerate():
    src = """
let xs = [10, 20, 30];
for (i, x) in xs { print(i, x); }
"""
    assert run(src) == "0 10\n1 20\n2 30\n"


def test_for_over_dict():
    src = """
let d = {"a": 1, "b": 2};
for (k, v) in d { print(k, v); }
"""
    assert run(src) == "a 1\nb 2\n"


def test_for_break_continue():
    src = """
let xs = [1, 2, 3, 4, 5];
for (x) in xs {
  if (x == 2) { continue; }
  if (x == 4) { break; }
  print(x);
}
"""
    assert run(src) == "1\n3\n"


def test_dict_print_format():
    src = 'let d = {"a": 1, "b": "x"}; print(d);'
    assert run(src) == '{"a": 1, "b": "x"}\n'


def test_del_missing_key_errors():
    with pytest.raises(Exception):
        run('let d = {"a": 1}; del(d, "z");')
