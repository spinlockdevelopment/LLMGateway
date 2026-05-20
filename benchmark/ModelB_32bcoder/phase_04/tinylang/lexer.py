import re
from tinylang.ast import Token
from tinylang.errors import LexError

def tokenize(source):
    tokens = []
    keywords = {
        'let', 'if', 'else', 'while', 'for', 'in', 'fn', 'return', 'break', 'continue',
        'true', 'false', 'nil'
    }
    token_specification = [
        ('NUMBER',   r'-?[0-9]+(?:|([.][0-9]+))'),
        ('STRING',   r'"([^"\\]*(?:\\.[^"\\]*)*)"'),
        ('IDENT',    r'[A-Za-z_][A-Za-z0-9_]*'),
        ('OP',       r'[+\-*/%==!<>]=?|&&|\|\|'),
        ('DELIM',    r'[(),{}\[\];:,]'),
        ('SKIP',     r'[ \t]+'),
        ('COMMENT',  r'//.*'),
        ('MISMATCH', r'.'),
    ]
    tok_regex = '|'.join('(?P<%s>%s)' % pair for pair in token_specification)
    get_token = re.compile(tok_regex).match
    line = 1
    col = 1
    mo = get_token(source)
    while mo:
        kind = mo.lastgroup
        value = mo.group()
        if kind == 'NUMBER':
            value = float(value)
        elif kind == 'STRING':
            value = value[1:-1]  # strip quotes
        elif kind == 'IDENT':
            if value in keywords:
                kind = value
        elif kind == 'SKIP':
            pass
        elif kind == 'COMMENT':
            pass
        elif kind == 'MISMATCH':
            raise LexError(f"Unexpected character '{value}' at line {line}, column {col}")
        else:
            tokens.append(Token(kind, value, line, col))
        col += len(value)
        mo = get_token(source, mo.end())
    return tokens
