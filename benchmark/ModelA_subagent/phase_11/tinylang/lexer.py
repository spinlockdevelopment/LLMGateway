"""Lexer for tinylang.

Turns a source string into a list of Token objects, ending with a single EOF
token. Whitespace and ``//`` line comments are skipped. Unrecognized input
raises :class:`tinylang.errors.LexError` whose ``str()`` includes the 1-based
line and column of the failing character.

Phase 10 promoted the previous module-local ``LexError`` shim into the public
``tinylang.errors`` hierarchy; this module re-exports the name so any code
that did ``from tinylang.lexer import LexError`` keeps working.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .errors import LexError


KEYWORDS = frozenset(
    {
        "let",
        "if",
        "else",
        "while",
        "for",
        "in",
        "fn",
        "return",
        "break",
        "continue",
        "true",
        "false",
        "nil",
    }
)

# Multi-character punctuation, checked before single-char punctuation.
_TWO_CHAR_PUNCT = ("==", "!=", "<=", ">=", "&&", "||")
_SINGLE_CHAR_PUNCT = frozenset(
    "+-*/%<>!=(){}[],;:."
)


@dataclass
class Token:
    kind: str
    value: object
    line: int
    col: int


def tokenize(source: str) -> list[Token]:
    """Tokenize ``source`` and return a list of Tokens ending with EOF."""
    tokens: list[Token] = []
    i = 0
    line = 1
    col = 1
    n = len(source)

    def err(msg: str, ln: int, cl: int) -> LexError:
        # ``LexError`` (from ``tinylang.errors``) carries line/col as
        # structured fields; its ``__str__`` formats them for display.
        return LexError(msg, line=ln, col=cl)

    while i < n:
        ch = source[i]

        # Whitespace handling: space, tab, CR, LF.
        if ch == "\n":
            i += 1
            line += 1
            col = 1
            continue
        if ch in (" ", "\t", "\r"):
            i += 1
            col += 1
            continue

        # Line comment: // ... to end of line (or EOF).
        if ch == "/" and i + 1 < n and source[i + 1] == "/":
            # Consume until newline or EOF; the newline itself is handled next iter.
            j = i + 2
            while j < n and source[j] != "\n":
                j += 1
            # column advance equals number of characters consumed on this line
            col += j - i
            i = j
            continue

        start_line = line
        start_col = col

        # String literal: double-quoted with escapes \n \t \" \\.
        if ch == '"':
            i += 1
            col += 1
            buf: list[str] = []
            terminated = False
            while i < n:
                c = source[i]
                if c == '"':
                    terminated = True
                    i += 1
                    col += 1
                    break
                if c == "\n":
                    # Newlines inside strings are not allowed.
                    raise err(
                        "unterminated string (newline in string literal)",
                        start_line,
                        start_col,
                    )
                if c == "\\":
                    if i + 1 >= n:
                        raise err(
                            "unterminated string escape", start_line, start_col
                        )
                    esc = source[i + 1]
                    if esc == "n":
                        buf.append("\n")
                    elif esc == "t":
                        buf.append("\t")
                    elif esc == '"':
                        buf.append('"')
                    elif esc == "\\":
                        buf.append("\\")
                    else:
                        raise err(
                            f"unknown escape sequence \\{esc}",
                            line,
                            col,
                        )
                    i += 2
                    col += 2
                    continue
                buf.append(c)
                i += 1
                col += 1
            if not terminated:
                raise err("unterminated string", start_line, start_col)
            tokens.append(
                Token(kind="STRING", value="".join(buf), line=start_line, col=start_col)
            )
            continue

        # Number literal: integer or float. Both stored as float.
        if ch.isdigit():
            j = i
            while j < n and source[j].isdigit():
                j += 1
            if j < n and source[j] == "." and j + 1 < n and source[j + 1].isdigit():
                j += 1
                while j < n and source[j].isdigit():
                    j += 1
            text = source[i:j]
            tokens.append(
                Token(kind="NUMBER", value=float(text), line=start_line, col=start_col)
            )
            col += j - i
            i = j
            continue

        # Identifier or keyword.
        if ch.isalpha() or ch == "_":
            j = i + 1
            while j < n and (source[j].isalnum() or source[j] == "_"):
                j += 1
            text = source[i:j]
            if text in KEYWORDS:
                tokens.append(
                    Token(kind="KEYWORD", value=text, line=start_line, col=start_col)
                )
            else:
                tokens.append(
                    Token(kind="IDENT", value=text, line=start_line, col=start_col)
                )
            col += j - i
            i = j
            continue

        # Two-character punctuation.
        if i + 1 < n:
            two = source[i : i + 2]
            if two in _TWO_CHAR_PUNCT:
                tokens.append(
                    Token(kind="PUNCT", value=two, line=start_line, col=start_col)
                )
                i += 2
                col += 2
                continue

        # Single-character punctuation.
        if ch in _SINGLE_CHAR_PUNCT:
            tokens.append(
                Token(kind="PUNCT", value=ch, line=start_line, col=start_col)
            )
            i += 1
            col += 1
            continue

        # Anything else is a lex error.
        raise err(f"unexpected character {ch!r}", start_line, start_col)

    tokens.append(Token(kind="EOF", value=None, line=line, col=col))
    return tokens
