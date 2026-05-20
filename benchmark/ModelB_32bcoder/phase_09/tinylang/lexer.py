from tinylang.ast import Token
from tinylang.errors import ParseError
import re

def tokenize(source: str) -> list:
    tokens = []
    token_specification = [
        ('NUMBER',   r'-?\b[0-9]+(?:\b|[.][0-9]+(?:[eE][-+]?\b[0-9]+)?)\b'),  # Integer or decimal number
        ('STRING',   r'"([^"\\]*(?:\\.[^"\\]*)*)"'),  # String
        ('IDENT',    r'[A-Za-z_][A-Za-z0-9_]*'),  # Identifiers
        ('OP',       r'[+\-*/%==!<>]=?'),  # Operators
        ('DELIM',    r'[(),;{}\[\]]'),  # Delimiters
        ('KEYWORD',  r'let|if|else|while|for|in|fn|return|break|continue|true|false|nil'),  # Keywords
        ('SKIP',     r'[ \t]+'),  # Skip over spaces and tabs
        ('NEWLINE',  r'(\n|\r(\n)?)'),  # Line endings
        ('MISMATCH', r'.'),  # Any other character
    ]
    tok_regex = '|'.join('(?P<%s>%s)' % pair for pair in token_specification)
    line_num = 1
    line_start = 0
    get_token = re.compile(tok_regex).match
    mo = get_token(source)
    while mo is not None:
        kind = mo.lastgroup
        value = mo.group()
        if kind == 'NUMBER':
            value = float(value)
        elif kind == 'STRING':
            value = value[1:-1]  # Remove quotes
        elif kind == 'NEWLINE':
            line_start = mo.end()
            line_num += 1
        elif kind == 'SKIP':
            pass
        elif kind == 'MISMATCH':
            raise ParseError(f'Unexpected character {value!r}', line_num, mo.start() - line_start + 1)
        else:
            column = mo.start() - line_start + 1
            tokens.append(Token(kind, value, line_num, column))
        mo = get_token(source, mo.end())
    return tokens
