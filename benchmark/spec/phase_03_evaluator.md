# Phase 3 — Evaluator: arithmetic, booleans, print

Read `spec/overall_brief.md` first.

## Goal

Implement an evaluator that can execute a tinylang program consisting of
expression statements. Numbers, booleans, strings, the four arithmetic ops,
comparisons, logical operators, and one built-in: `print`.

## Scope

- Produce `tinylang/evaluator.py` exposing `run(source: str) -> str`.
- Produce `tinylang/builtins.py` with at least `print`. Other built-ins land in
  later phases.
- `run` parses `source`, executes the resulting AST, and returns everything
  written by `print` calls as a single string (each `print` ends with `\n`).
- The function `run` does **not** print to real stdout. Tests capture by
  comparing the return value of `run`.

## Operators

- `+ - * / %` on numbers behave like Python with `float` semantics
  (so `3 / 2 == 1.5`). `/` by zero must raise a runtime error.
- `+` on two strings concatenates. `+` between a number and a string is a
  runtime error.
- `== !=` work on any two values (cross-type compares are well-defined: equal
  only if same type and same value).
- `< > <= >=` are defined for two numbers and for two strings (lexicographic).
  Cross-type compare → runtime error.
- `&&` and `||` short-circuit. They return one of the operand values (not
  necessarily a bool), like JavaScript. Falsy = `nil | false | 0`. Everything
  else is truthy. `!x` returns a bool.

## `print`

`print` accepts any number of args. It joins them with a single space,
appends `"\n"`, and writes to the program's captured output buffer. Number
formatting: integers (numbers with no fractional part) print without a decimal
(`5`, not `5.0`); other numbers print with as few digits as Python's default
`repr` (using `repr(float)` with the trailing `.0` removed for integers).
Strings print without quotes. Booleans print as `true` / `false`. Nil prints as
`nil`.

## What "done" looks like

```python
run("print(1 + 2);")              # "3\n"
run("print(\"hi\" + \" you\");")  # "hi you\n"
run("print(1 < 2);")              # "true\n"
run("print(true && \"x\");")      # "x\n"
run("print(2 / 0);")              # raises a runtime error
```

## Out of scope

- Variables and `let` — phase 4.
- Functions, control flow — later phases.
- Polished error types — phase 10. For now use plain `Exception` whose message
  includes a hint about what went wrong.
