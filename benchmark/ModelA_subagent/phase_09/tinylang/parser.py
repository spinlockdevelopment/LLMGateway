"""Recursive-descent parser for tinylang.

Consumes tokens from ``tinylang.lexer`` and produces a ``Program`` AST.
Grammar is defined in ``spec/overall_brief.md`` §3.

A parse error raises an Exception whose ``str()`` includes the 1-based line
and column of the offending token. The dedicated ``ParseError`` class will
arrive in phase 10.
"""

from __future__ import annotations

from typing import Union

from .ast import (
    Assign,
    BinaryOp,
    Block,
    BoolLit,
    BreakStmt,
    Call,
    ContinueStmt,
    DictLit,
    ExprStmt,
    FnDecl,
    FnLit,
    ForStmt,
    Identifier,
    IfStmt,
    Index,
    LetStmt,
    ListLit,
    NilLit,
    NumberLit,
    Program,
    ReturnStmt,
    StringLit,
    UnaryOp,
    WhileStmt,
)
from .lexer import Token, tokenize


class ParseError(Exception):
    """Raised on invalid input during parsing.

    Phase 10 will refine this into the public error hierarchy. For now its
    ``str()`` includes ``line`` and ``col``.
    """


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    # ------------------------------------------------------------------ utils

    def _peek(self, offset: int = 0) -> Token:
        idx = self.pos + offset
        if idx >= len(self.tokens):
            return self.tokens[-1]  # EOF
        return self.tokens[idx]

    def _advance(self) -> Token:
        tok = self.tokens[self.pos]
        if tok.kind != "EOF":
            self.pos += 1
        return tok

    def _at_end(self) -> bool:
        return self._peek().kind == "EOF"

    def _check(self, kind: str, value: object = None) -> bool:
        tok = self._peek()
        if tok.kind != kind:
            return False
        if value is not None and tok.value != value:
            return False
        return True

    def _match(self, kind: str, value: object = None) -> bool:
        if self._check(kind, value):
            self._advance()
            return True
        return False

    def _check_punct(self, *values: str) -> bool:
        tok = self._peek()
        return tok.kind == "PUNCT" and tok.value in values

    def _match_punct(self, *values: str) -> bool:
        if self._check_punct(*values):
            self._advance()
            return True
        return False

    def _check_kw(self, *values: str) -> bool:
        tok = self._peek()
        return tok.kind == "KEYWORD" and tok.value in values

    def _match_kw(self, *values: str) -> bool:
        if self._check_kw(*values):
            self._advance()
            return True
        return False

    def _expect_punct(self, value: str) -> Token:
        tok = self._peek()
        if tok.kind == "PUNCT" and tok.value == value:
            return self._advance()
        raise self._error(f"expected '{value}'", tok)

    def _expect_kw(self, value: str) -> Token:
        tok = self._peek()
        if tok.kind == "KEYWORD" and tok.value == value:
            return self._advance()
        raise self._error(f"expected '{value}'", tok)

    def _expect_ident(self) -> Token:
        tok = self._peek()
        if tok.kind == "IDENT":
            return self._advance()
        raise self._error("expected identifier", tok)

    def _error(self, msg: str, tok: Token | None = None) -> ParseError:
        if tok is None:
            tok = self._peek()
        return ParseError(f"{msg} at line {tok.line}, col {tok.col}")

    # ----------------------------------------------------------------- program

    def parse_program(self) -> Program:
        stmts: list = []
        while not self._at_end():
            stmts.append(self.parse_statement())
        return Program(stmts=stmts)

    # --------------------------------------------------------------- statements

    def parse_statement(self):
        tok = self._peek()
        if tok.kind == "KEYWORD":
            v = tok.value
            if v == "let":
                return self.parse_let()
            if v == "if":
                return self.parse_if()
            if v == "while":
                return self.parse_while()
            if v == "for":
                return self.parse_for()
            if v == "fn":
                # `fn IDENT (...)` is a declaration; `fn (...)` is an
                # expression statement holding a function literal.
                nxt = self._peek(1)
                if nxt.kind == "IDENT":
                    return self.parse_fn_decl()
                # Fall through to expression statement.
            if v == "return":
                return self.parse_return()
            if v == "break":
                self._advance()
                self._expect_punct(";")
                return BreakStmt()
            if v == "continue":
                self._advance()
                self._expect_punct(";")
                return ContinueStmt()
        if tok.kind == "PUNCT" and tok.value == "{":
            return self.parse_block()
        return self.parse_expr_stmt()

    def parse_let(self) -> LetStmt:
        self._expect_kw("let")
        name_tok = self._expect_ident()
        self._expect_punct("=")
        value = self.parse_expression()
        self._expect_punct(";")
        return LetStmt(name=name_tok.value, value=value)

    def parse_if(self) -> IfStmt:
        self._expect_kw("if")
        self._expect_punct("(")
        cond = self.parse_expression()
        self._expect_punct(")")
        then_block = self.parse_block()
        else_block = None
        if self._match_kw("else"):
            if self._check_kw("if"):
                # Nest the next IfStmt directly so `else if` chains correctly.
                else_block = self.parse_if()
            else:
                else_block = self.parse_block()
        return IfStmt(cond=cond, then_block=then_block, else_block=else_block)

    def parse_while(self) -> WhileStmt:
        self._expect_kw("while")
        self._expect_punct("(")
        cond = self.parse_expression()
        self._expect_punct(")")
        body = self.parse_block()
        return WhileStmt(cond=cond, body=body)

    def parse_for(self) -> ForStmt:
        self._expect_kw("for")
        self._expect_punct("(")
        first = self._expect_ident()
        names = [first.value]
        if self._match_punct(","):
            second = self._expect_ident()
            names.append(second.value)
        self._expect_punct(")")
        self._expect_kw("in")
        iterable = self.parse_expression()
        body = self.parse_block()
        return ForStmt(names=names, iterable=iterable, body=body)

    def parse_fn_decl(self) -> FnDecl:
        self._expect_kw("fn")
        name_tok = self._expect_ident()
        self._expect_punct("(")
        params = self.parse_params()
        self._expect_punct(")")
        body = self.parse_block()
        return FnDecl(name=name_tok.value, params=params, body=body)

    def parse_return(self) -> ReturnStmt:
        self._expect_kw("return")
        if self._check_punct(";"):
            self._advance()
            return ReturnStmt(value=None)
        value = self.parse_expression()
        self._expect_punct(";")
        return ReturnStmt(value=value)

    def parse_block(self) -> Block:
        self._expect_punct("{")
        stmts: list = []
        while not self._check_punct("}") and not self._at_end():
            stmts.append(self.parse_statement())
        self._expect_punct("}")
        return Block(stmts=stmts)

    def parse_expr_stmt(self) -> ExprStmt:
        expr = self.parse_expression()
        self._expect_punct(";")
        return ExprStmt(expr=expr)

    def parse_params(self) -> list:
        params: list = []
        if self._check_punct(")"):
            return params
        first = self._expect_ident()
        params.append(first.value)
        while self._match_punct(","):
            nxt = self._expect_ident()
            params.append(nxt.value)
        return params

    # -------------------------------------------------------------- expressions

    def parse_expression(self):
        return self.parse_assignment()

    def parse_assignment(self):
        # Right-associative. Parse the left side as logic_or; if `=` follows
        # and the left is a valid lvalue, recurse to consume the RHS.
        expr = self.parse_logic_or()
        if self._check_punct("="):
            eq_tok = self._peek()
            self._advance()
            value = self.parse_assignment()
            if not isinstance(expr, (Identifier, Index)):
                raise self._error("invalid assignment target", eq_tok)
            return Assign(target=expr, value=value)
        return expr

    def parse_logic_or(self):
        expr = self.parse_logic_and()
        while self._check_punct("||"):
            self._advance()
            right = self.parse_logic_and()
            expr = BinaryOp(op="||", left=expr, right=right)
        return expr

    def parse_logic_and(self):
        expr = self.parse_equality()
        while self._check_punct("&&"):
            self._advance()
            right = self.parse_equality()
            expr = BinaryOp(op="&&", left=expr, right=right)
        return expr

    def parse_equality(self):
        expr = self.parse_comparison()
        while self._check_punct("==", "!="):
            op = self._advance().value
            right = self.parse_comparison()
            expr = BinaryOp(op=op, left=expr, right=right)
        return expr

    def parse_comparison(self):
        expr = self.parse_term()
        while self._check_punct("<", ">", "<=", ">="):
            op = self._advance().value
            right = self.parse_term()
            expr = BinaryOp(op=op, left=expr, right=right)
        return expr

    def parse_term(self):
        expr = self.parse_factor()
        while self._check_punct("+", "-"):
            op = self._advance().value
            right = self.parse_factor()
            expr = BinaryOp(op=op, left=expr, right=right)
        return expr

    def parse_factor(self):
        expr = self.parse_unary()
        while self._check_punct("*", "/", "%"):
            op = self._advance().value
            right = self.parse_unary()
            expr = BinaryOp(op=op, left=expr, right=right)
        return expr

    def parse_unary(self):
        if self._check_punct("!", "-"):
            op = self._advance().value
            operand = self.parse_unary()
            return UnaryOp(op=op, operand=operand)
        return self.parse_call()

    def parse_call(self):
        expr = self.parse_primary()
        while True:
            if self._check_punct("("):
                self._advance()
                args = self.parse_args()
                self._expect_punct(")")
                expr = Call(callee=expr, args=args)
            elif self._check_punct("["):
                self._advance()
                key = self.parse_expression()
                self._expect_punct("]")
                expr = Index(target=expr, key=key)
            else:
                break
        return expr

    def parse_args(self) -> list:
        args: list = []
        if self._check_punct(")"):
            return args
        args.append(self.parse_expression())
        while self._match_punct(","):
            args.append(self.parse_expression())
        return args

    def parse_primary(self):
        tok = self._peek()
        if tok.kind == "NUMBER":
            self._advance()
            return NumberLit(value=float(tok.value))
        if tok.kind == "STRING":
            self._advance()
            return StringLit(value=tok.value)
        if tok.kind == "KEYWORD":
            if tok.value == "true":
                self._advance()
                return BoolLit(value=True)
            if tok.value == "false":
                self._advance()
                return BoolLit(value=False)
            if tok.value == "nil":
                self._advance()
                return NilLit()
            if tok.value == "fn":
                return self.parse_fn_lit()
        if tok.kind == "IDENT":
            self._advance()
            return Identifier(name=tok.value)
        if tok.kind == "PUNCT":
            if tok.value == "(":
                self._advance()
                expr = self.parse_expression()
                self._expect_punct(")")
                return expr
            if tok.value == "[":
                return self.parse_list_lit()
            if tok.value == "{":
                return self.parse_dict_lit()
        raise self._error("unexpected token", tok)

    def parse_list_lit(self) -> ListLit:
        self._expect_punct("[")
        items: list = []
        if self._check_punct("]"):
            self._advance()
            return ListLit(items=items)
        items.append(self.parse_expression())
        while self._match_punct(","):
            # Allow trailing comma.
            if self._check_punct("]"):
                break
            items.append(self.parse_expression())
        self._expect_punct("]")
        return ListLit(items=items)

    def parse_dict_lit(self) -> DictLit:
        self._expect_punct("{")
        pairs: list = []
        if self._check_punct("}"):
            self._advance()
            return DictLit(pairs=pairs)
        pairs.append(self._parse_pair())
        while self._match_punct(","):
            # Allow trailing comma.
            if self._check_punct("}"):
                break
            pairs.append(self._parse_pair())
        self._expect_punct("}")
        return DictLit(pairs=pairs)

    def _parse_pair(self):
        key = self.parse_expression()
        self._expect_punct(":")
        value = self.parse_expression()
        return (key, value)

    def parse_fn_lit(self) -> FnLit:
        self._expect_kw("fn")
        self._expect_punct("(")
        params = self.parse_params()
        self._expect_punct(")")
        body = self.parse_block()
        return FnLit(params=params, body=body)


def parse(source_or_tokens: Union[str, list]) -> Program:
    """Parse a source string or token list and return a ``Program`` AST."""
    if isinstance(source_or_tokens, str):
        tokens = tokenize(source_or_tokens)
    else:
        tokens = list(source_or_tokens)
    parser = _Parser(tokens)
    program = parser.parse_program()
    return program
