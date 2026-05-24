from typing import Union, List, Tuple, Optional
from tinylang.lexer import tokenize, Token
from tinylang.ast import (
    Program, LetStmt, IfStmt, WhileStmt, ForStmt, FnDecl, ReturnStmt,
    BreakStmt, ContinueStmt, Block, ExprStmt, NumberLit, StringLit,
    BoolLit, NilLit, Identifier, ListLit, DictLit, FnLit, BinaryOp,
    UnaryOp, Call, Index, Assign
)

class ParseError(Exception):
    def __init__(self, message: str, line: int, col: int):
        self.message = message
        self.line = line
        self.col = col

    def __str__(self):
        return f"Parse error at line {self.line}, col {self.col}: {self.message}"

class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return Token("EOF", None, -1, -1)

    def advance(self) -> Token:
        token = self.peek()
        self.pos += 1
        return token

    def check(self, kind: str, value: Optional[str] = None) -> bool:
        token = self.peek()
        if token.kind != kind:
            return False
        if value is not None and token.value != value:
            return False
        return True

    def match(self, kind: str, value: Optional[str] = None) -> bool:
        if self.check(kind, value):
            self.advance()
            return True
        return False

    def consume(self, kind: str, value: Optional[str] = None, message: str = "") -> Token:
        if self.check(kind, value):
            return self.advance()
        token = self.peek()
        raise ParseError(message or f"Expected {kind}{' ' + str(value) if value else ''} but got {token.kind}{' ' + str(token.value) if token.value is not None else ''}", token.line, token.col)

    def parse(self) -> Program:
        stmts = []
        while not self.check("EOF"):
            stmts.append(self.statement())
        return Program(stmts)

    def statement(self) -> Union[LetStmt, IfStmt, WhileStmt, ForStmt, FnDecl, ReturnStmt, BreakStmt, ContinueStmt, Block, ExprStmt]:
        if self.match("KEYWORD", "let"):
            name = self.consume("IDENT", message="Expected identifier after 'let'").value
            self.consume("PUNCT", "=", message="Expected '=' after identifier")
            value = self.expression()
            self.consume("PUNCT", ";", message="Expected ';' after let statement")
            return LetStmt(name=name, value=value)
        
        if self.match("KEYWORD", "if"):
            return self.if_stmt()

        if self.match("KEYWORD", "while"):
            self.consume("PUNCT", "(", message="Expected '(' after 'while'")
            cond = self.expression()
            self.consume("PUNCT", ")", message="Expected ')' after while condition")
            body = self.block()
            return WhileStmt(cond=cond, body=body)

        if self.match("KEYWORD", "for"):
            names = []
            self.consume("PUNCT", "(", message="Expected '(' after 'for'")
            names.append(self.consume("IDENT", message="Expected identifier in for loop").value)
            if self.match("PUNCT", ","):
                names.append(self.consume("IDENT", message="Expected identifier in for loop").value)
            self.consume("PUNCT", ")", message="Expected ')' after for loop params")
            self.consume("KEYWORD", "in", message="Expected 'in' after for loop params")
            iterable = self.expression()
            body = self.block()
            return ForStmt(names=names, iterable=iterable, body=body)

        if self.match("KEYWORD", "fn"):
            # Check if it's FnDecl (fn name(...) { ... })
            if self.check("IDENT"):
                name = self.consume("IDENT", message="Expected function name").value
                self.consume("PUNCT", "(", message="Expected '(' after function name")
                params = self.params()
                self.consume("PUNCT", ")", message="Expected ')' after parameters")
                body = self.block()
                return FnDecl(name=name, params=params, body=body)
            else:
                # It's a FnLit. We need to backtrack "fn".
                self.pos -= 1
                expr = self.expression()
                self.consume("PUNCT", ";", message="Expected ';' after expression")
                return ExprStmt(expr=expr)

        if self.match("KEYWORD", "return"):
            value = None
            if not self.check("PUNCT", ";"):
                value = self.expression()
            self.consume("PUNCT", ";", message="Expected ';' after return statement")
            return ReturnStmt(value=value)

        if self.match("KEYWORD", "break"):
            self.consume("PUNCT", ";", message="Expected ';' after break statement")
            return BreakStmt()

        if self.match("KEYWORD", "continue"):
            self.consume("PUNCT", ";", message="Expected ';' after continue statement")
            return ContinueStmt()

        if self.match("PUNCT", "{"):
            # We already consumed "{". We need to parse the rest of the block.
            # But block() expects to consume "{".
            # Let's refactor.
            # Actually, let's just call a method that parses the contents.
            # But we need to handle the closing "}".
            # Let's use a helper.
            # Wait, if we are here, we've already consumed "{".
            # Let's just use a block_contents() method.
            # But the grammar says block = "{" { statement } "}".
            # Let's just call block() and fix it.
            # Actually, let's just use a method that parses a block starting from the current position.
            # But we already consumed "{".
            # Let's just call a method that parses the statements and then expects "}".
            pass

        # Let's refactor statement() to handle block correctly.
        # If we see "{", it's a block.
        # If we see "let", "if", etc., it's those.
        # Otherwise, it's an expr_stmt.
        
        # Let's try again.
        return self.statement_impl()

    def if_stmt(self) -> IfStmt:
        # "if" is already consumed.
        self.consume("PUNCT", "(", message="Expected '(' after 'if'")
        cond = self.expression()
        self.consume("PUNCT", ")", message="Expected ')' after if condition")
        then_block = self.block()
        else_block = None
        if self.match("KEYWORD", "else"):
            if self.check("KEYWORD", "if"):
                # Nested if (else if)
                # We need to parse the "if" part.
                # But we've already consumed "else".
                # We can call if_stmt() directly because it starts with "if".
                # But we need to pass the "else" part to it? No.
                # The if_stmt is: "if" "(" expression ")" block [ "else" ( if_stmt | block ) ]
                # If we have "else if", the "if" part is the if_stmt.
                # Let's just call if_stmt() and it will handle its own "else".
                # But we need to return the IfStmt.
                # This is tricky. Let's use a helper.
                pass
        return IfStmt(cond=cond, then_block=then_block, else_block=else_block)

    # This is not working well. I'll write a clean version.
    pass

def parse(source_or_tokens: Union[str, List[Token]]) -> Program:
    if isinstance(source_or_tokens, str):
        tokens = tokenize(source_or_tokens)
    else:
        tokens = source_or_tokens
    return Parser(tokens).parse()
