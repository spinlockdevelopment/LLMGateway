from tinylang.token import Token
from tinylang.ast import Program, FnDecl, FnLit, Call, ReturnStmt
from tinylang.errors import TinylangError, RuntimeError as TinyRuntimeError
from tinylang.evaluator import Function, eval_fn_decl, eval_fn_lit, eval_call, eval_return_stmt, ReturnStmt
from tinylang.environment import Environment

import re

def tokenize(source):
    tokens = []
    token_specification = [
        ('NUMBER',   r'-?\b[0-9]+(\b|[.][0-9]+)\b'),
        ('STRING',   r'"([^"\\]*(\\.[^"\\]*)*)"'),
        ('IDENT',    r'[A-Za-z_][A-Za-z0-9_]*'),
        ('OP',       r'[+\-*/%==!<>]=?'),
        ('DELIM',    r'[(),;{}\[\],:]'),
        ('SKIP',     r'[ \t]+'),
        ('COMMENT',  r'//.*'),
        ('MISMATCH', r'.'),
    ]
    tok_regex = '|'.join('(?P<%s>%s)' % pair for pair in token_specification)
    get_token = re.compile(tok_regex).match
    line = 1
    line_start = 0
    pos = 0
    mo = get_token(source)
    while mo is not None:
        kind = mo.lastgroup
        value = mo.group()
        if kind == 'NUMBER':
            value = float(value)
        elif kind == 'STRING':
            value = value[1:-1]
        elif kind == 'COMMENT':
            pass
        elif kind == 'SKIP':
            pass
        elif kind == 'MISMATCH':
            raise TinylangError(f'Unexpected character {value!r} at line {line}, column {pos - line_start + 1}')
        else:
            column = pos - line_start + 1
            tokens.append(Token(kind, value, line, column))
        pos = mo.end()
        mo = get_token(source, pos)
        if mo is None and pos < len(source):
            raise TinylangError(f'Unexpected character {source[pos]!r} at line {line}, column {pos - line_start + 1}')
        while pos >= line_start + len(source.splitlines()[line - 1]) + 1:
            line += 1
            line_start = pos
    return tokens
