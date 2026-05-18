# Phase 1 — Lexer

Read `spec/overall_brief.md` first.

## Goal

Implement the lexer that turns tinylang source into a stream of tokens.

## Scope

- Produce `tinylang/lexer.py` exposing `tokenize(source: str) -> list[Token]`.
- Produce `tinylang/__init__.py` (may be empty).
- A `Token` is a dataclass (or equivalent) with the fields below.
- Skip whitespace and `//` line comments.
- Emit one `EOF` token at the end.
- On unrecognized character, raise an exception with `line` and `col` in the
  message (the actual error class can land in phase 10 — for now any exception
  whose `str()` includes the line+col is fine).

## Token shape (required public contract)

```python
from dataclasses import dataclass

@dataclass
class Token:
    kind: str        # see kinds below
    value: object    # str for IDENT/STRING/punct, float for NUMBER, None for KEYWORD/EOF
    line: int        # 1-based
    col: int         # 1-based, column where the token starts
```

Tests will access `tok.kind`, `tok.value`, `tok.line`, `tok.col`. Keep these
attribute names.

## Token kinds

| kind        | when emitted                                                       |
|-------------|--------------------------------------------------------------------|
| `NUMBER`    | integer or float literal; `value` is a Python `float`              |
| `STRING`    | double-quoted string with escapes `\n \t \" \\`; `value` is `str`  |
| `IDENT`     | identifier; `value` is the identifier text                         |
| `KEYWORD`   | one of: `let if else while for in fn return break continue true false nil`; `value` is the keyword text |
| `PUNCT`     | one of: `+ - * / % == != < > <= >= && || ! = ( ) { } [ ] , ; : .`; `value` is the punctuation text |
| `EOF`       | one and only one; emitted at end                                   |

Multi-character punctuation (`==`, `!=`, `<=`, `>=`, `&&`, `||`) must be lexed as
one token, not two.

## Line and column tracking

- Lines are 1-based, starting at 1. A newline increments line, resets col to 1.
- Columns are 1-based, counted by characters (not bytes), starting at 1.
- `token.line` and `token.col` point to the **first character** of the token.

## Edge cases to handle

- Empty input → just one `EOF` token.
- Trailing comment without newline.
- String spanning multiple lines is **not** allowed; raise an error if a `\n`
  appears inside an unterminated string. (Escapes like `\n` are fine.)
- Unterminated string at EOF → error with the line/col of the opening quote.
- A keyword embedded in a longer identifier (e.g. `iffy`) is an identifier, not
  the keyword `if`.

## What "done" looks like

`tokenize("let x = 1 + 2;")` returns tokens with kinds
`KEYWORD IDENT PUNCT NUMBER PUNCT NUMBER PUNCT EOF` and values
`"let" "x" "=" 1.0 "+" 2.0 ";" None`, with correct line/col for each.

## Out of scope

- AST nodes — phase 2.
- Any execution. Don't import `parser` or `evaluator`.
- Error classes — phase 10. A plain `Exception` is fine here.
