from dataclasses import dataclass
from typing import List


@dataclass
class Token:
    kind: str
    value: object
    line: int
    col: int


KEYWORDS = frozenset({
    "let", "if", "else", "while", "for", "in",
    "fn", "return", "break", "continue",
    "true", "false", "nil",
})

PUNCTUATION = frozenset({
    "+", "-", "*", "/", "%",
    "==", "!=", "<", ">", "<=", ">=",
    "&&", "||",
    "!", "=",
    "(", ")", "{", "}", "[", "]",
    ",", ";", ":", ".",
})

# Multi-char punctuation sorted by length descending so we try longer matches first
MULTI_CHAR_PUNCT = ["==", "!=", "<=", ">=", "&&", "||"]


def tokenize(source: str) -> List[Token]:
    tokens: List[Token] = []
    i = 0
    line = 1
    col = 1
    length = len(source)

    while i < length:
        ch = source[i]

        # Newline
        if ch == '\n':
            line += 1
            col = 1
            i += 1
            continue

        # Whitespace (space, tab, CR)
        if ch in (' ', '\t', '\r'):
            col += 1
            i += 1
            continue

        # Single-line comment
        if ch == '/' and i + 1 < length and source[i + 1] == '/':
            # Skip until end of line
            while i < length and source[i] != '\n':
                i += 1
            continue

        # Start of token
        start_line = line
        start_col = col

        # String literal
        if ch == '"':
            i += 1
            col += 1
            s = []
            while i < length and source[i] != '"':
                if source[i] == '\n':
                    raise Exception(f"unterminated string at line {start_line}, col {start_col}")
                if source[i] == '\\':
                    i += 1
                    col += 1
                    if i >= length:
                        raise Exception(f"unterminated string at line {start_line}, col {start_col}")
                    esc = source[i]
                    if esc == 'n':
                        s.append('\n')
                    elif esc == 't':
                        s.append('\t')
                    elif esc == '"':
                        s.append('"')
                    elif esc == '\\':
                        s.append('\\')
                    else:
                        s.append(esc)
                    i += 1
                    col += 1
                else:
                    s.append(source[i])
                    i += 1
                    col += 1
            if i >= length:
                raise Exception(f"unterminated string at line {start_line}, col {start_col}")
            # Consume closing quote
            i += 1
            col += 1
            tokens.append(Token(kind="STRING", value=''.join(s), line=start_line, col=start_col))
            continue

        # Number literal
        if ch.isdigit():
            num_str = []
            while i < length and (source[i].isdigit() or source[i] == '.'):
                num_str.append(source[i])
                i += 1
                col += 1
            tokens.append(Token(kind="NUMBER", value=float(''.join(num_str)), line=start_line, col=start_col))
            continue

        # Identifier or keyword
        if ch.isalpha() or ch == '_':
            ident = []
            while i < length and (source[i].isalnum() or source[i] == '_'):
                ident.append(source[i])
                i += 1
                col += 1
            word = ''.join(ident)
            if word in KEYWORDS:
                tokens.append(Token(kind="KEYWORD", value=word, line=start_line, col=start_col))
            else:
                tokens.append(Token(kind="IDENT", value=word, line=start_line, col=start_col))
            continue

        # Punctuation (multi-char first, then single-char)
        matched = False
        for p in MULTI_CHAR_PUNCT:
            if source[i:i+len(p)] == p:
                tokens.append(Token(kind="PUNCT", value=p, line=start_line, col=start_col))
                i += len(p)
                col += len(p)
                matched = True
                break
        if matched:
            continue

        if ch in PUNCTUATION:
            tokens.append(Token(kind="PUNCT", value=ch, line=start_line, col=start_col))
            i += 1
            col += 1
            continue

        # Unrecognized character
        raise Exception(f"unrecognized character '{ch}' at line {start_line}, col {start_col}")

    # EOF token
    tokens.append(Token(kind="EOF", value=None, line=line, col=col))
    return tokens
