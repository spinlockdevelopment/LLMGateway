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


def tokenize(source: str) -> List[Token]:
    tokens: List[Token] = []
    i = 0
    line = 1
    col = 1
    src_len = len(source)

    while i < src_len:
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
        if ch == '/' and i + 1 < src_len and source[i + 1] == '/':
            # Skip until end of line
            while i < src_len and source[i] != '\n':
                i += 1
            continue

        # Start of token
        start_line = line
        start_col = col

        # Number
        if ch.isdigit():
            num_start = i
            has_dot = False
            i += 1
            while i < src_len and source[i].isdigit():
                i += 1
            if i < src_len and source[i] == '.':
                has_dot = True
                i += 1
                while i < src_len and source[i].isdigit():
                    i += 1
            tokens.append(Token("NUMBER", float(source[num_start:i]), start_line, start_col))
            col = start_col + (i - num_start)
            continue

        # String
        if ch == '"':
            i += 1  # skip opening quote
            s_start = i
            while i < src_len and source[i] != '"':
                if source[i] == '\n':
                    raise Exception(f"unterminated string at line {start_line}, col {start_col}")
                if source[i] == '\\':
                    i += 1  # skip escaped char
                    if i >= src_len:
                        raise Exception(f"unterminated string at line {start_line}, col {start_col}")
                i += 1
            if i >= src_len:
                raise Exception(f"unterminated string at line {start_line}, col {start_col}")
            raw = source[s_start:i]
            # Process escapes
            processed = []
            j = 0
            while j < len(raw):
                if raw[j] == '\\' and j + 1 < len(raw):
                    nc = raw[j + 1]
                    if nc == 'n':
                        processed.append('\n')
                    elif nc == 't':
                        processed.append('\t')
                    elif nc == '"':
                        processed.append('"')
                    elif nc == '\\':
                        processed.append('\\')
                    else:
                        processed.append('\\')
                        processed.append(nc)
                    j += 2
                else:
                    processed.append(raw[j])
                    j += 1
            tokens.append(Token("STRING", ''.join(processed), start_line, start_col))
            i += 1  # skip closing quote
            col = start_col + (i - num_start if 'num_start' in dir() else 1)
            # recalculate col properly
            col = start_col + (i - start_col)
            continue

        # Identifier or keyword
        if ch.isalpha() or ch == '_':
            id_start = i
            i += 1
            while i < src_len and (source[i].isalnum() or source[i] == '_'):
                i += 1
            text = source[id_start:i]
            if text in KEYWORDS:
                tokens.append(Token("KEYWORD", text, start_line, start_col))
            else:
                tokens.append(Token("IDENT", text, start_line, start_col))
            col = start_col + (i - id_start)
            continue

        # Punctuation (multi-char first)
        if ch in ('&', '|', '!', '<', '>', '=', '+', '-', '*', '/', '%', '(', ')', '{', '}', '[', ']', ',', ';', ':', '.'):
            # Try two-char punctuators
            two = source[i:i+2] if i + 1 < src_len else ch
            if two in ('==', '!=', '<=', '>=', '&&', '||'):
                tokens.append(Token("PUNCT", two, start_line, start_col))
                i += 2
                col = start_col + 2
                continue
            # Single char
            if ch in PUNCTUATION:
                tokens.append(Token("PUNCT", ch, start_line, start_col))
                i += 1
                col = start_col + 1
                continue

        # Unrecognized character
        raise Exception(f"unrecognized character '{ch}' at line {start_line}, col {start_col}")

    tokens.append(Token("EOF", None, line, col))
    return tokens
