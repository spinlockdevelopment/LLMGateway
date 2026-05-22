from typing import List, Optional, Union

from tinylang.lexer import tokenize
from tinylang.ast import (
    Program, LetStmt, IfStmt, WhileStmt, ForStmt, FnDecl,
    ReturnStmt, BreakStmt, ContinueStmt, Block, ExprStmt,
    NumberLit, StringLit, BoolLit, NilLit, Identifier,
    ListLit, DictLit, FnLit, BinaryOp, UnaryOp, Call, Index, Assign,
)


class ParseError(Exception):
    def __init__(self, msg: str, line: int = 0, col: int = 0):
        if line and col:
            msg = f"line {line}, col {col}: {msg}"
        super().__init__(msg)


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def current(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return self.tokens[-1]  # EOF

    def peek(self):
        return self.current()

    def advance(self):
        tok = self.current()
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return tok

    def expect_keyword(self, kw: str):
        tok = self.current()
        if tok.kind != "KEYWORD" or tok.value != kw:
            raise ParseError(f"expected '{kw}', got '{tok.value}'", tok.line, tok.col)
        return self.advance()

    def expect_punct(self, p: str):
        tok = self.current()
        if tok.kind != "PUNCT" or tok.value != p:
            raise ParseError(f"expected '{p}', got '{tok.value}'", tok.line, tok.col)
        return self.advance()

    def expect_ident(self):
        tok = self.current()
        if tok.kind != "IDENT":
            raise ParseError(f"expected identifier, got '{tok.value}'", tok.line, tok.col)
        return self.advance()

    def parse(self, source=None):
        if source is not None:
            self.tokens = tokenize(source)
            self.pos = 0
        return self.parse_program()

    def parse_program(self) -> Program:
        stmts = []
        while self.peek().kind != "EOF":
            stmts.append(self.parse_stmt())
        return Program(stmts=stmts)

    def parse_stmt(self):
        tok = self.peek()

        if tok.kind == "KEYWORD" and tok.value == "let":
            return self.parse_let_stmt()
        elif tok.kind == "KEYWORD" and tok.value == "if":
            return self.parse_if_stmt()
        elif tok.kind == "KEYWORD" and tok.value == "while":
            return self.parse_while_stmt()
        elif tok.kind == "KEYWORD" and tok.value == "for":
            return self.parse_for_stmt()
        elif tok.kind == "KEYWORD" and tok.value == "fn":
            return self.parse_fn_decl()
        elif tok.kind == "KEYWORD" and tok.value == "return":
            return self.parse_return_stmt()
        elif tok.kind == "KEYWORD" and tok.value == "break":
            return self.parse_break_stmt()
        elif tok.kind == "KEYWORD" and tok.value == "continue":
            return self.parse_continue_stmt()
        else:
            return self.parse_expr_stmt()

    def parse_let_stmt(self) -> LetStmt:
        self.expect_keyword("let")
        name_tok = self.expect_ident()
        self.expect_punct("=")
        value = self.parse_expr()
        self.expect_punct(";")
        return LetStmt(name=name_tok.value, value=value)

    def parse_if_stmt(self) -> IfStmt:
        self.expect_keyword("if")
        self.expect_punct("(")
        cond = self.parse_expr()
        self.expect_punct(")")
        then_block = self.parse_block()
        else_block = None
        if self.peek().kind == "KEYWORD" and self.peek().value == "else":
            self.advance()
            if self.peek().kind == "KEYWORD" and self.peek().value == "if":
                else_block = self.parse_if_stmt()
            else:
                else_block = self.parse_block()
        return IfStmt(cond=cond, then_block=then_block, else_block=else_block)

    def parse_while_stmt(self) -> WhileStmt:
        self.expect_keyword("while")
        self.expect_punct("(")
        cond = self.parse_expr()
        self.expect_punct(")")
        body = self.parse_block()
        return WhileStmt(cond=cond, body=body)

    def parse_for_stmt(self) -> ForStmt:
        self.expect_keyword("for")
        self.expect_punct("(")
        names = []
        names.append(self.expect_ident())
        while self.peek().kind == "PUNCT" and self.peek().value == ",":
            self.advance()
            names.append(self.expect_ident())
        self.expect_punct(")")
        self.expect_keyword("in")
        iterable = self.parse_expr()
        body = self.parse_block()
        return ForStmt(names=names, iterable=iterable, body=body)

    def parse_fn_decl(self) -> FnDecl:
        self.expect_keyword("fn")
        name_tok = self.expect_ident()
        self.expect_punct("(")
        params = []
        if self.peek().kind != ")":
            params.append(self.expect_ident())
            while self.peek().kind == "PUNCT" and self.peek().value == ",":
                self.advance()
                params.append(self.expect_ident())
        self.expect_punct(")")
        body = self.parse_block()
        return FnDecl(name=name_tok.value, params=params, body=body)

    def parse_return_stmt(self) -> ReturnStmt:
        self.expect_keyword("return")
        value = None
        if self.peek().kind != ";":
            value = self.parse_expr()
        self.expect_punct(";")
        return ReturnStmt(value=value)

    def parse_break_stmt(self) -> BreakStmt:
        self.expect_keyword("break")
        self.expect_punct(";")
        return BreakStmt()

    def parse_continue_stmt(self) -> ContinueStmt:
        self.expect_keyword("continue")
        self.expect_punct(";")
        return ContinueStmt()

    def parse_expr_stmt(self) -> ExprStmt:
        expr = self.parse_expr()
        if self.peek().kind == "PUNCT" and self.peek().value == ";":
            self.advance()
        return ExprStmt(expr=expr)

    def parse_block(self) -> Block:
        self.expect_punct("{")
        stmts = []
        while self.peek().kind != "}" and self.peek().kind != "EOF":
            stmts.append(self.parse_stmt())
        self.expect_punct("}")
        return Block(stmts=stmts)

    # ---- Expression parsing (precedence climbing) ----

    def parse_expr(self):
        return self.parse_assign()

    def parse_assign(self):
        left = self.parse_or()
        if self.peek().kind == "PUNCT" and self.peek().value == "=":
            # Only allow Identifier or Index as target
            if not isinstance(left, (Identifier, Index)):
                tok = self.current()
                raise ParseError(
                    f"invalid assignment target: {type(left).__name__}",
                    tok.line, tok.col
                )
            self.advance()
            right = self.parse_assign()  # right-associative
            return Assign(target=left, value=right)
        return left

    def parse_or(self):
        left = self.parse_and()
        while self.peek().kind == "PUNCT" and self.peek().value == "||":
            self.advance()
            right = self.parse_and()
            left = BinaryOp(op="||", left=left, right=right)
        return left

    def parse_and(self):
        left = self.parse_comparison()
        while self.peek().kind == "PUNCT" and self.peek().value == "&&":
            self.advance()
            right = self.parse_comparison()
            left = BinaryOp(op="&&", left=left, right=right)
        return left

    def parse_comparison(self):
        left = self.parse_addition()
        while self.peek().kind == "PUNCT" and self.peek().value in ("==", "!=", "<", ">", "<=", ">="):
            op = self.advance().value
            right = self.parse_addition()
            left = BinaryOp(op=op, left=left, right=right)
        return left

    def parse_addition(self):
        left = self.parse_multiplication()
        while self.peek().kind == "PUNCT" and self.peek().value in ("+", "-"):
            op = self.advance().value
            right = self.parse_multiplication()
            left = BinaryOp(op=op, left=left, right=right)
        return left

    def parse_multiplication(self):
        left = self.parse_unary()
        while self.peek().kind == "PUNCT" and self.peek().value in ("*", "/", "%"):
            op = self.advance().value
            right = self.parse_unary()
            left = BinaryOp(op=op, left=left, right=right)
        return left

    def parse_unary(self):
        if self.peek().kind == "PUNCT" and self.peek().value in ("!", "-"):
            op = self.advance().value
            operand = self.parse_unary()
            return UnaryOp(op=op, operand=operand)
        return self.parse_primary_with_postfix()

    def parse_primary(self):
        tok = self.peek()

        # Literals
        if tok.kind == "NUMBER":
            self.advance()
            return NumberLit(value=tok.value)
        if tok.kind == "STRING":
            self.advance()
            return StringLit(value=tok.value)
        if tok.kind == "KEYWORD" and tok.value == "true":
            self.advance()
            return BoolLit(value=True)
        if tok.kind == "KEYWORD" and tok.value == "false":
            self.advance()
            return BoolLit(value=False)
        if tok.kind == "KEYWORD" and tok.value == "nil":
            self.advance()
            return NilLit()

        # Identifier
        if tok.kind == "IDENT":
            self.advance()
            return Identifier(name=tok.value)

        # List literal
        if tok.kind == "PUNCT" and tok.value == "[":
            return self.parse_list_lit()

        # Dict literal
        if tok.kind == "PUNCT" and tok.value == "{":
            return self.parse_dict_lit()

        # Function literal
        if tok.kind == "KEYWORD" and tok.value == "fn":
            return self.parse_fn_lit()

        # Parenthesized expression
        if tok.kind == "PUNCT" and tok.value == "(":
            self.advance()
            expr = self.parse_expr()
            self.expect_punct(")")
            return expr

        raise ParseError(
            f"unexpected token: {tok.value}",
            tok.line, tok.col
        )

    def parse_list_lit(self) -> ListLit:
        self.expect_punct("[")
        items = []
        if self.peek().kind != "]":
            items.append(self.parse_expr())
            while self.peek().kind == "PUNCT" and self.peek().value == ",":
                self.advance()
                if self.peek().kind == "]":
                    break  # trailing comma
                items.append(self.parse_expr())
        self.expect_punct("]")
        return ListLit(items=items)

    def parse_dict_lit(self) -> DictLit:
        self.expect_punct("{")
        pairs = []
        if self.peek().kind != "}":
            key = self.parse_expr()
            self.expect_punct(":")
            val = self.parse_expr()
            pairs.append((key, val))
            while self.peek().kind == "PUNCT" and self.peek().value == ",":
                self.advance()
                if self.peek().kind == "}":
                    break  # trailing comma
                key = self.parse_expr()
                self.expect_punct(":")
                val = self.parse_expr()
                pairs.append((key, val))
        self.expect_punct("}")
        return DictLit(pairs=pairs)

    def parse_fn_lit(self) -> FnLit:
        self.expect_keyword("fn")
        self.expect_punct("(")
        params = []
        if self.peek().kind != ")":
            params.append(self.expect_ident())
            while self.peek().kind == "PUNCT" and self.peek().value == ",":
                self.advance()
                params.append(self.expect_ident())
        self.expect_punct(")")
        body = self.parse_block()
        return FnLit(params=params, body=body)

    # ---- Post-primary: call and index ----
    # These are handled by a post-parse step after parse_primary returns.
    # We need to modify parse_primary to also handle call/index chaining.

    def parse_primary_with_postfix(self):
        """Parse a primary expression followed by optional call and index postfixes."""
        tok = self.peek()

        # Literals
        if tok.kind == "NUMBER":
            self.advance()
            node = NumberLit(value=tok.value)
        elif tok.kind == "STRING":
            self.advance()
            node = StringLit(value=tok.value)
        elif tok.kind == "KEYWORD" and tok.value == "true":
            self.advance()
            node = BoolLit(value=True)
        elif tok.kind == "KEYWORD" and tok.value == "false":
            self.advance()
            node = BoolLit(value=False)
        elif tok.kind == "KEYWORD" and tok.value == "nil":
            self.advance()
            node = NilLit()
        elif tok.kind == "IDENT":
            self.advance()
            node = Identifier(name=tok.value)
        elif tok.kind == "PUNCT" and tok.value == "[":
            node = self.parse_list_lit()
        elif tok.kind == "PUNCT" and tok.value == "{":
            node = self.parse_dict_lit()
        elif tok.kind == "KEYWORD" and tok.value == "fn":
            node = self.parse_fn_lit()
        elif tok.kind == "PUNCT" and tok.value == "(":
            self.advance()
            node = self.parse_expr()
            self.expect_punct(")")
        else:
            raise ParseError(
                f"unexpected token: {tok.value}",
                tok.line, tok.col
            )

        # Handle call and index postfixes
        node = self.parse_postfix(node)
        return node

    def parse_postfix(self, node):
        while True:
            if self.peek().kind == "PUNCT" and self.peek().value == "(":
                self.advance()
                args = []
                if self.peek().kind != ")":
                    args.append(self.parse_expr())
                    while self.peek().kind == "PUNCT" and self.peek().value == ",":
                        self.advance()
                        args.append(self.parse_expr())
                self.expect_punct(")")
                node = Call(callee=node, args=args)
            elif self.peek().kind == "PUNCT" and self.peek().value == "[":
                self.advance()
                key = self.parse_expr()
                self.expect_punct("]")
                node = Index(target=node, key=key)
            else:
                break
        return node


def parse(source_or_tokens):
    """Parse source string or token list into a Program AST."""
    if isinstance(source_or_tokens, str):
        tokens = tokenize(source_or_tokens)
    else:
        tokens = list(source_or_tokens)

    parser = Parser(tokens)
    return parser.parse_program()
