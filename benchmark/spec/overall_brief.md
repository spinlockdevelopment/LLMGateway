# tinylang — Overall Brief

You are building **tinylang**, a small dynamically-typed scripting language, in Python 3.11+.
The benchmark builds this language in 12 incremental phases. Each phase extends the
work of the prior phases. After the final phase you should be able to run real
tinylang programs with closures, lists, dicts, and a small standard library written
in tinylang itself.

This document defines the **target language semantics** and the **expected code
layout**. Every phase brief references this file. Read it once at the start of
each phase before you begin.

---

## 1. Language at a glance

tinylang is C-flavored, dynamically typed, with first-class functions.

```tinylang
// Single-line comments only.

let x = 10;
let name = "world";

if (x > 5) {
  print("hello, " + name);
} else {
  print("small");
}

fn fib(n) {
  if (n < 2) { return n; }
  return fib(n - 1) + fib(n - 2);
}

print(fib(10));   // 55

let make_counter = fn() {
  let n = 0;
  return fn() { n = n + 1; return n; };
};
let c = make_counter();
print(c()); print(c()); print(c());  // 1 2 3

let xs = [1, 2, 3];
push(xs, 4);
for (i, v) in xs { print(i, v); }

let d = {"a": 1, "b": 2};
for (k, v) in d { print(k, v); }
```

## 2. Lexical structure

- Whitespace (space, tab, CR, LF) separates tokens and is otherwise ignored.
- Comments start with `//` and run to end of line.
- Identifiers: `[A-Za-z_][A-Za-z0-9_]*`.
- Keywords (reserved, never identifiers):
  `let if else while for in fn return break continue true false nil`
- Numbers: integer (`42`) and float (`3.14`); both stored as Python `float`.
- Strings: double-quoted, with escapes `\n \t \" \\`.
- Punctuation / operators:
  `+ - * / %  == != < > <= >=  && || !  = (  )  {  }  [  ]  ,  ;  :  .`
- An unrecognized character at any position is a lex error with line and column.

## 3. Grammar (informal EBNF)

```
program       = { statement } ;
statement     = let_stmt | if_stmt | while_stmt | for_stmt | fn_decl
              | return_stmt | break_stmt | continue_stmt | block | expr_stmt ;
let_stmt      = "let" IDENT "=" expression ";" ;
if_stmt       = "if" "(" expression ")" block [ "else" ( if_stmt | block ) ] ;
while_stmt    = "while" "(" expression ")" block ;
for_stmt      = "for" "(" IDENT [ "," IDENT ] ")" "in" expression block ;
fn_decl       = "fn" IDENT "(" [ params ] ")" block ;
return_stmt   = "return" [ expression ] ";" ;
break_stmt    = "break" ";" ;
continue_stmt = "continue" ";" ;
block         = "{" { statement } "}" ;
expr_stmt     = expression ";" ;
params        = IDENT { "," IDENT } ;

// Expressions, lowest to highest precedence:
expression    = assignment ;
assignment    = logic_or | (lvalue "=" assignment) ;
logic_or      = logic_and { "||" logic_and } ;
logic_and     = equality { "&&" equality } ;
equality      = comparison { ( "==" | "!=" ) comparison } ;
comparison    = term { ( "<" | ">" | "<=" | ">=" ) term } ;
term          = factor { ( "+" | "-" ) factor } ;
factor        = unary { ( "*" | "/" | "%" ) unary } ;
unary         = ( "!" | "-" ) unary | call ;
call          = primary { "(" [ args ] ")" | "[" expression "]" } ;
primary       = NUMBER | STRING | "true" | "false" | "nil" | IDENT
              | "(" expression ")" | list_lit | dict_lit | fn_lit ;
list_lit      = "[" [ expression { "," expression } [ "," ] ] "]" ;
dict_lit      = "{" [ pair { "," pair } [ "," ] ] "}" ;
pair          = expression ":" expression ;
fn_lit        = "fn" "(" [ params ] ")" block ;
lvalue        = IDENT | call ;  // for assignment: only IDENT, xs[i], d[k] are valid lvalues
args          = expression { "," expression } ;
```

`fn name(...) { ... }` is sugar for `let name = fn(...) { ... };`.

## 4. Values and semantics

| Tinylang   | Python repr           |
|------------|-----------------------|
| number     | `float`               |
| string     | `str`                 |
| bool       | `bool`                |
| nil        | `None`                |
| list       | `list`                |
| dict       | `dict` (string keys; other keys allowed but stringified for display) |
| function   | a `Function` object holding params, body AST, and a captured environment |

- `+` on two strings concatenates. `+` on numbers adds. Mixed → runtime error.
- `/` is float division. `%` is the standard remainder.
- Comparisons require same type; mixing → runtime error (except `==` / `!=` which
  may compare unlike values and return `false` / `true`).
- `&&` and `||` short-circuit and return one of the operand values
  (truthy/falsy rules: `nil`, `false`, and `0` are falsy; everything else truthy).
- Indexing: `xs[i]` (0-based; negative not supported), `d["k"]`. Out-of-bounds list
  index or missing dict key → runtime error.
- Functions close over their defining environment by reference.

## 5. Built-in functions (final set after phase 11)

| name              | meaning                                                 |
|-------------------|---------------------------------------------------------|
| `print(...args)`  | prints args joined by `" "`, ends with newline          |
| `len(x)`          | length of string / list / dict                          |
| `push(xs, v)`     | append v to list xs (mutates), returns nil              |
| `pop(xs)`         | remove and return last; error on empty                  |
| `keys(d)`         | list of dict keys                                       |
| `values(d)`       | list of dict values                                     |
| `has(d, k)`       | bool: does dict d contain key k                         |
| `del(d, k)`       | remove key k from dict d, returns nil                   |
| `str(x)`          | string representation                                   |
| `num(x)`          | parse string/number to number; error otherwise          |
| `range(n)` or `range(a,b)` | list of numbers (stdlib in phase 11 if not earlier) |

## 6. Expected module layout

After phase 12 the workdir contains:

```
tinylang/
  __init__.py
  lexer.py
  parser.py
  ast.py           # AST node dataclasses
  evaluator.py
  environment.py
  builtins.py
  errors.py
  cli.py
stdlib.tl          # added in phase 11
tests/             # populated by the harness at self-eval time
```

You may add additional helper modules. Keep each module focused.

## 7. Programming rules

- Pure Python 3.11+, standard library only. No third-party dependencies.
- Code must run on the workdir Python (`python` on PATH).
- Tests are run with `pytest -q` from the workdir.
- Public surface (what tests import):
  - `from tinylang.lexer import tokenize`  → returns list of `Token` instances.
  - `from tinylang.parser import parse`    → returns a `Program` AST node.
  - `from tinylang.evaluator import run`   → executes a source string and returns
    captured stdout as a string. Signature: `run(source: str) -> str`.
  - `from tinylang.errors import TinylangError, ParseError, RuntimeError as TinyRuntimeError`
    (or equivalent; the public name `TinylangError` is the umbrella).
- The exact `Token` and AST shapes are up to you, but they must be inspectable
  enough that tests for phases 1 and 2 (which check token fields and AST node
  types) pass. See those phase briefs for the contract.

## 8. Quality bar

Your code is judged on:

- **Accuracy** — does it pass the acceptance tests for the phase?
- **Completeness** — does it cover the brief? Edge cases, error messages, code
  organization. Tests do not exhaustively cover every line of the brief — assume
  the reviewer will read your code.

Do not add features beyond the current phase's scope. Do not refactor prior-phase
code unless the current phase requires it.

## 9. Phase index

1. Lexer
2. Parser → AST
3. Evaluator: arithmetic, booleans, print
4. Variables, assignment, blocks, lexical scope
5. Control flow: if/else, while, break, continue
6. Functions: declarations, calls, recursion
7. Closures
8. Lists
9. Dicts and `for ... in ...`
10. Error model: parse + runtime errors with line/col and stack traces
11. Standard library written in tinylang itself
12. CLI and REPL
