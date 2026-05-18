# Phase 5 — Control flow: if / while / break / continue

Read `spec/overall_brief.md` first.

## Goal

Add `if`/`else`, `while` loops, and the loop control statements `break` and
`continue`.

## Scope

- Extend the evaluator to handle `IfStmt`, `WhileStmt`, `BreakStmt`,
  `ContinueStmt`.
- `if (cond) {...} [else {...}]`: evaluate `cond`, check truthiness using the
  same rules as phase 3 (`nil | false | 0` are falsy), execute the
  corresponding block. `else if` chains evaluate as expected (handled by the
  parser's nested `IfStmt`).
- `while (cond) {...}`: repeatedly evaluate `cond` and execute the body while
  truthy. The body executes in a fresh child env (block scope) each iteration.
- `break` exits the nearest enclosing `while`. `continue` skips to the next
  iteration's condition check.
- `break` or `continue` **outside** of a loop is a runtime error. Tests do not
  exhaustively check this, but reviewers will.

## Implementation hint

The common idiom is to raise small internal exceptions `BreakSignal` and
`ContinueSignal` inside the evaluator and catch them at the `while` loop.
This is fine. Keep those signal classes private to `evaluator.py`.

## Examples

```tinylang
let i = 0;
let sum = 0;
while (i < 5) {
  sum = sum + i;
  i = i + 1;
}
print(sum);       // 10

let i = 0;
while (true) {
  if (i == 3) { break; }
  if (i == 1) { i = i + 1; continue; }
  print(i);
  i = i + 1;
}
// prints: 0  2
```

## Out of scope

- `for` loops over iterables — phase 9 (after dicts and lists exist).
- Functions and recursion — phase 6.
