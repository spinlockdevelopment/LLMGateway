# Phase 2 — Parser

Read `spec/overall_brief.md` first. The grammar lives there.

## Goal

Implement a recursive-descent parser that consumes the token stream from phase 1
and produces an AST.

## Scope

- Produce `tinylang/ast.py` defining AST node dataclasses (or equivalent).
- Produce `tinylang/parser.py` exposing `parse(source_or_tokens) -> Program`.
- `parse` must accept either a source string or a token list. If given a string,
  call `tokenize` from `tinylang.lexer` internally.
- Cover the **full** grammar in `overall_brief.md` §3 (every statement form, every
  expression precedence level, list/dict/function literals, the `fn` declaration
  sugar).
- A parse error raises an exception whose `str()` includes the line and column
  of the offending token. A proper `ParseError` class lands in phase 10.

## Required AST node names

Tests will check `type(node).__name__`. Use these exact class names:

```
Program            stmts: list

LetStmt            name: str, value: Expr
IfStmt             cond: Expr, then_block: Block, else_block: Block | None
WhileStmt          cond: Expr, body: Block
ForStmt            names: list[str], iterable: Expr, body: Block
FnDecl             name: str, params: list[str], body: Block
ReturnStmt         value: Expr | None
BreakStmt
ContinueStmt
Block              stmts: list
ExprStmt           expr: Expr

NumberLit          value: float
StringLit          value: str
BoolLit            value: bool
NilLit
Identifier         name: str
ListLit            items: list[Expr]
DictLit            pairs: list[tuple[Expr, Expr]]
FnLit              params: list[str], body: Block

BinaryOp           op: str, left: Expr, right: Expr     # for + - * / % == != < > <= >= && ||
UnaryOp            op: str, operand: Expr                # for ! and unary -
Call               callee: Expr, args: list[Expr]
Index              target: Expr, key: Expr
Assign             target: Expr, value: Expr             # target is Identifier | Index
```

Dataclasses are encouraged but not required, as long as the attribute names and
class names match.

## Notes on the grammar

- `fn name(...) { body }` desugars to `FnDecl(name, params, body)`. It is **not**
  represented as `LetStmt + FnLit`; tests will see a `FnDecl` node.
- `else if` chains: an `else if` should produce nested `IfStmt` in the
  `else_block` slot (you may choose to wrap it in a `Block` or store the
  `IfStmt` directly — both are accepted as long as evaluation in later phases is
  consistent).
- Precedence and associativity must match `overall_brief.md` §3. All binary
  operators are left-associative; assignment is right-associative.
- Trailing commas inside list and dict literals are allowed.
- `Index` is used for both list and dict access: `xs[0]`, `d["k"]`.
- Assignment targets are restricted to `Identifier` and `Index`. Anything else
  on the left of `=` is a parse error.

## What "done" looks like

```python
prog = parse("let x = 1 + 2 * 3;")
# prog.stmts is [LetStmt(name='x', value=BinaryOp('+', NumberLit(1.0),
#                                                     BinaryOp('*', NumberLit(2.0), NumberLit(3.0))))]
```

## Out of scope

- Execution / evaluation.
- Static checks. The parser only enforces grammar.
- Polished error messages with suggestions — phase 10 is the place for that.
