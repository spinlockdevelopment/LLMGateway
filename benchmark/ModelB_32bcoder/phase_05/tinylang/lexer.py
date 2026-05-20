from tinylang.ast import Token
from tinylang.errors import LexError
import re

def tokenize(source: str) -> list[Token]:
    tokens = []
    line = 1
    col = 1
    pos = 0
    source_len = len(source)
    token_specification = [
        ('NUMBER',   r'-?\b[0-9]+(?:\.?[0-9]*)\b'),  # Integer or decimal number
        ('STRING',   r'".*?"'),                      # String
        ('IDENT',    r'[A-Za-z_][A-Za-z0-9_]*'),         # Identifiers
        ('OP',       r'[+\-*/%&|!<>]=?'),                # Operators
        ('DELIM',    r'[(),;{}\[\]]'),                 # Delimiters
        ('SKIP',     r'[ \t]+'),                         # Skip over spaces and tabs
        ('NEWLINE',  r'\n'),                             # Line endings
        ('MISMATCH', r'.'),                               # Any other character
    ]
    tok_regex = '|'.join('(?P<%s>%s)' % pair for pair in token_specification)
    get_token = re.compile(tok_regex).match
    while pos < source_len:
        mo = get_token(source, pos)
        if not mo:
            raise LexError(f"Unexpected character '{source[pos]}' at line {line}, column {col}")
        kind = mo.lastgroup
        value = mo.group()
        if kind == 'NUMBER':
            value = float(value)
        elif kind == 'STRING':
            value = value[1:-1]  # Remove quotes
        elif kind == 'SKIP':
            pos = mo.end()
            col += len(value)
            continue
        elif kind == 'NEWLINE':
            line += 1
            col = 1
        elif kind == 'MISMATCH':
            raise LexError(f"Unexpected character '{value}' at line {line}, column {col}")
        else:
            col += len(value)
        pos = mo.end()
        if kind in ('NUMBER', 'STRING', 'IDENT', 'OP', 'DELIM'):
            tokens.append(Token(kind, value, line, col))
    return tokens
