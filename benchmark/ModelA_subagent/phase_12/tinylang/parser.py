"""Recursive-descent parser for tinylang.

Consumes tokens from ``tinylang.lexer`` and produces a ``Program`` AST.
Grammar is defined in ``spec/overall_brief.md`` §3.

A parse error raises :class:`tinylang.errors.ParseError` whose ``str()``
includes the 1-based line and column of the offending token.

Phase 10 notes
--------------
This phase moves the previously-local ``ParseError`` into ``tinylang.errors``
and also annotates expression AST nodes with the source position of their
leading token. Runtime errors raised by the evaluator pick those positions
up so a ``foo`` lookup that fails reports the line/col where ``foo``
appeared, not just a vague "somewhere in the program" message.
"""

from __future__ import annotations

from typing import Any, Union

from .errors import ParseError
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


def _attach(node: Any, tok: Token) -> Any:
    """Stamp ``tok``'s ``line``/``col`` onto an AST node.

    The AST dataclasses don't declare ``line``/``col`` fields (their public
    schema is fixed by phase 2), so we attach them as ordinary attributes.
    The evaluator pulls them off via ``getattr(node, "line", None)`` when
    formatting runtime errors — missing attributes simply yield ``None``,
    which the error class renders as a location-free message.
    """
    node.line = tok.line
    node.col = tok.col
    return node


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
        # ``ParseError`` (from ``tinylang.errors``) stores line/col as fields
        # and renders them via ``__str__``; no manual formatting needed.
        return ParseError(msg, line=tok.line, col=tok.col)

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
        let_tok = self._peek()
        self._expect_kw("let")
        name_tok = self._expect_ident()
        self._expect_punct("=")
        value = self.parse_expression()
        self._expect_punct(";")
        stmt = LetStmt(name=name_tok.value, value=value)
        # Stamp the ``let`` keyword's position so a re-declaration error can
        # point at the offending statement.
        return _attach(stmt, let_tok)

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
        fn_tok = self._peek()
        self._expect_kw("fn")
        name_tok = self._expect_ident()
        self._expect_punct("(")
        params = self.parse_params()
        self._expect_punct(")")
        body = self.parse_block()
        decl = FnDecl(name=name_tok.value, params=params, body=body)
        return _attach(decl, fn_tok)

    def parse_return(self) -> ReturnStmt:
        ret_tok = self._peek()
        self._expect_kw("return")
        if self._check_punct(";"):
            self._advance()
            return _attach(ReturnStmt(value=None), ret_tok)
        value = self.parse_expression()
        self._expect_punct(";")
        return _attach(ReturnStmt(value=value), ret_tok)

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
            return _attach(Assign(target=expr, value=value), eq_tok)
        return expr

    def parse_logic_or(self):
        expr = self.parse_logic_and()
        while self._check_punct("||"):
            op_tok = self._peek()
            self._advance()
            right = self.parse_logic_and()
            expr = _attach(BinaryOp(op="||", left=expr, right=right), op_tok)
        return expr

    def parse_logic_and(self):
        expr = self.parse_equality()
        while self._check_punct("&&"):
            op_tok = self._peek()
            self._advance()
            right = self.parse_equality()
            expr = _attach(BinaryOp(op="&&", left=expr, right=right), op_tok)
        return expr

    def parse_equality(self):
        expr = self.parse_comparison()
        while self._check_punct("==", "!="):
            op_tok = self._peek()
            op = self._advance().value
            right = self.parse_comparison()
            expr = _attach(BinaryOp(op=op, left=expr, right=right), op_tok)
        return expr

    def parse_comparison(self):
        expr = self.parse_term()
        while self._check_punct("<", ">", "<=", ">="):
            op_tok = self._peek()
            op = self._advance().value
            right = self.parse_term()
            expr = _attach(BinaryOp(op=op, left=expr, right=right), op_tok)
        return expr

    def parse_term(self):
        expr = self.parse_factor()
        while self._check_punct("+", "-"):
            op_tok = self._peek()
            op = self._advance().value
            right = self.parse_factor()
            expr = _attach(BinaryOp(op=op, left=expr, right=right), op_tok)
        return expr

    def parse_factor(self):
        expr = self.parse_unary()
        while self._check_punct("*", "/", "%"):
            op_tok = self._peek()
            op = self._advance().value
            right = self.parse_unary()
            expr = _attach(BinaryOp(op=op, left=expr, right=right), op_tok)
        return expr

    def parse_unary(self):
        if self._check_punct("!", "-"):
            op_tok = self._peek()
            op = self._advance().value
            operand = self.parse_unary()
            return _attach(UnaryOp(op=op, operand=operand), op_tok)
        return self.parse_call()

    def parse_call(self):
        expr = self.parse_primary()
        while True:
            if self._check_punct("("):
                # The ``(`` token marks the call site — that's the line we
                # want in the runtime stack trace, not the callee's line.
                paren_tok = self._peek()
                self._advance()
                args = self.parse_args()
                self._expect_punct(")")
                expr = _attach(Call(callee=expr, args=args), paren_tok)
            elif self._check_punct("["):
                bracket_tok = self._peek()
                self._advance()
                key = self.parse_expression()
                self._expect_punct("]")
                expr = _attach(Index(target=expr, key=key), bracket_tok)
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
            return _attach(NumberLit(value=float(tok.value)), tok)
        if tok.kind == "STRING":
            self._advance()
            return _attach(StringLit(value=tok.value), tok)
        if tok.kind == "KEYWORD":
            if tok.value == "true":
                self._advance()
                return _attach(BoolLit(value=True), tok)
            if tok.value == "false":
                self._advance()
                return _attach(BoolLit(value=False), tok)
            if tok.value == "nil":
                self._advance()
                return _attach(NilLit(), tok)
            if tok.value == "fn":
                return self.parse_fn_lit()
        if tok.kind == "IDENT":
            self._advance()
            # Identifier lookup is the most common runtime error site (an
            # ``undefined variable`` report needs the exact source position).
            return _attach(Identifier(name=tok.value), tok)
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
        open_tok = self._peek()
        self._expect_punct("[")
        items: list = []
        if self._check_punct("]"):
            self._advance()
            return _attach(ListLit(items=items), open_tok)
        items.append(self.parse_expression())
        while self._match_punct(","):
            # Allow trailing comma.
            if self._check_punct("]"):
                break
            items.append(self.parse_expression())
        self._expect_punct("]")
        return _attach(ListLit(items=items), open_tok)

    def parse_dict_lit(self) -> DictLit:
        open_tok = self._peek()
        self._expect_punct("{")
        pairs: list = []
        if self._check_punct("}"):
            self._advance()
            return _attach(DictLit(pairs=pairs), open_tok)
        pairs.append(self._parse_pair())
        while self._match_punct(","):
            # Allow trailing comma.
            if self._check_punct("}"):
                break
            pairs.append(self._parse_pair())
        self._expect_punct("}")
        return _attach(DictLit(pairs=pairs), open_tok)

    def _parse_pair(self):
        key = self.parse_expression()
        self._expect_punct(":")
        value = self.parse_expression()
        return (key, value)

    def parse_fn_lit(self) -> FnLit:
        fn_tok = self._peek()
        self._expect_kw("fn")
        self._expect_punct("(")
        params = self.parse_params()
        self._expect_punct(")")
        body = self.parse_block()
        return _attach(FnLit(params=params, body=body), fn_tok)


def parse(source_or_tokens: Union[str, list]) -> Program:
    """Parse a source string or token list and return a ``Program`` AST."""
    if isinstance(source_or_tokens, str):
        tokens = tokenize(source_or_tokens)
    else:
        tokens = list(source_or_tokens)
    parser = _Parser(tokens)
    program = parser.parse_program()
    return program
