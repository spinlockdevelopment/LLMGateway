from typing import Union, List, Tuple, Optional
from tinylang.lexer import tokenize, Token
from tinylang.ast import (
    Program, LetStmt, IfStmt, WhileStmt, ForStmt, FnDecl, ReturnStmt,
    BreakStmt, ContinueStmt, Block, ExprStmt, NumberLit, StringLit,
    BoolLit, NilLit, Identifier, ListLit, DictLit, FnLit, BinaryOp,
    UnaryOp, Call, Index, Assign, Statement
)

class ParseError(Exception):
    def __init__(self, message: str, line: int, col: int):
        self.message = message
        self.line = line
        self.col = col

    def __str__(self):
        return f"Parse error at line {self.line}, col {self.col}: {self.message}"

def parse(source: str) -> Program:
    from tinylang.lexer import tokenize
    tokens = tokenize(source)
    return Parser(tokens).parse()

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

    def statement(self) -> Statement:
        if self.match("KEYWORD", "let"):
            name = self.consume("IDENT", message="Expected identifier after 'let'").value
            self.consume("PUNCT", "=", message="Expected '=' after identifier")
            expr = self.expression()
            self.consume("PUNCT", ";", message="Expected ';' after let statement")
            return LetStmt(name=name, value=expr)
        
        if self.match("KEYWORD", "if"):
            return self.if_stmt()

        if self.match("KEYWORD", "while"):
            self.consume("PUNCT", "(", message="Expected '(' after 'while'")
            cond = self.expression()
            self.consume("PUNCT", ")", message="Expected ')' after while condition")
            body = self.block()
            return WhileStmt(cond=cond, body=body)

        if self.match("KEYWORD", "for"):
            return self.for_stmt()

        if self.match("KEYWORD", "fn"):
            return self.fn_decl()

        if self.match("KEYWORD", "return"):
            val = None
            if not self.check("PUNCT", ";"):
                val = self.expression()
            self.consume("PUNCT", ";", message="Expected ';' after return statement")
            return ReturnStmt(value=val)

        if self.match("KEYWORD", "break"):
            self.consume("PUNCT", ";", message="Expected ';' after break statement")
            return BreakStmt()

        if self.match("KEYWORD", "continue"):
            self.consume("PUNCT", ";", message="Expected ';' after continue statement")
            return ContinueStmt()

        if self.match("PUNCT", "{"):
            return self.block_contents()

        expr = self.expression()
        self.consume("PUNCT", ";", message="Expected ';' after expression statement")
        return ExprStmt(expr=expr)

    def if_stmt(self) -> IfStmt:
        self.consume("PUNCT", "(", message="Expected '(' after 'if'")
        cond = self.expression()
        self.consume("PUNCT", ")", message="Expected ')' after 'if' condition")
        then_branch = self.block()
        else_branch = None
        if self.match("KEYWORD", "else"):
            if self.match("KEYWORD", "if"):
                else_branch = self.if_stmt()
            else:
                else_branch = self.block()
        return IfStmt(cond=cond, then_block=then_branch, else_block=else_branch)

    def for_stmt(self) -> ForStmt:
        self.consume("PUNCT", "(", message="Expected '(' after 'for'")
        names = []
        if self.match("KEYWORD", "let"):
            pass
        
        while True:
            name = self.consume("IDENT", message="Expected identifier in for loop").value
            names.append(name)
            if not self.match("PUNCT", ","):
                break
        
        self.consume("PUNCT", ")", message="Expected ')' after names")
        self.consume("KEYWORD", "in", message="Expected 'in' after names")
        iterable = self.expression()
        body = self.block()
        return ForStmt(names=names, iterable=iterable, body=body)

    def fn_decl(self) -> FnDecl:
        name = self.consume("IDENT", message="Expected function name").value
        self.consume("PUNCT", "(", message="Expected '(' after function name")
        params = self.params()
        self.consume("PUNCT", ")", message="Expected ')' after parameters")
        body = self.block()
        return FnDecl(name=name, params=params, body=body)

    def params(self) -> List[str]:
        params = []
        if not self.check("PUNCT", ")"):
            while True:
                param_name = self.consume("IDENT", message="Expected parameter name").value
                if self.match("PUNCT", ":"):
                    self.consume("IDENT", message="Expected type after ':'")
                params.append(param_name)
                if not self.match("PUNCT", ","):
                    break
        return params

    def block(self) -> Block:
        self.consume("PUNCT", "{", message="Expected '{' to start block")
        return self.block_contents()

    def block_contents(self) -> Block:
        stmts = []
        while not self.check("PUNCT", "}") and not self.check("EOF"):
            stmts.append(self.statement())
        self.consume("PUNCT", "}", message="Expected '}' to end block")
        return Block(stmts=stmts)

    def expression(self) -> Union[BinaryOp, UnaryOp, Call, Index, Assign, NumberLit, StringLit, BoolLit, NilLit, Identifier, ListLit, DictLit, FnLit]:
        return self.assignment()

    def assignment(self) -> Union[BinaryOp, UnaryOp, Call, Index, Assign, NumberLit, StringLit, BoolLit, NilLit, Identifier, ListLit, DictLit, FnLit]:
        expr = self.logical_or()
        if self.match("PUNCT", "="):
            if not isinstance(expr, (Identifier, Index)):
                raise ParseError("Invalid assignment target", self.peek().line, self.peek().col)
            value = self.assignment()
            return Assign(target=expr, value=value)
        return expr

    def logical_or(self) -> Union[BinaryOp, UnaryOp, Call, Index, Assign, NumberLit, StringLit, BoolLit, NilLit, Identifier, ListLit, DictLit, FnLit]:
        expr = self.logical_and()
        while self.match("PUNCT", "||"):
            right = self.logical_and()
            expr = BinaryOp(left=expr, op="||", right=right)
        return expr

    def logical_and(self) -> Union[BinaryOp, UnaryOp, Call, Index, Assign, NumberLit, StringLit, BoolLit, NilLit, Identifier, ListLit, DictLit, FnLit]:
        expr = self.equality()
        while self.match("PUNCT", "&&"):
            right = self.equality()
            expr = BinaryOp(left=expr, op="&&", right=right)
        return expr

    def equality(self) -> Union[BinaryOp, UnaryOp, Call, Index, Assign, NumberLit, StringLit, BoolLit, NilLit, Identifier, ListLit, DictLit, FnLit]:
        expr = self.comparison()
        while True:
            if self.match("PUNCT", "=="):
                right = self.comparison()
                expr = BinaryOp(left=expr, op="==", right=right)
            elif self.match("PUNCT", "!="):
                right = self.comparison()
                expr = BinaryOp(left=expr, op="!=", right=right)
            else:
                break
        return expr

    def comparison(self) -> Union[BinaryOp, UnaryOp, Call, Index, Assign, NumberLit, StringLit, BoolLit, NilLit, Identifier, ListLit, DictLit, FnLit]:
        expr = self.term()
        while True:
            if self.match("PUNCT", "<"):
                right = self.term()
                expr = BinaryOp(left=expr, op="<", right=right)
            elif self.match("PUNCT", ">"):
                right = self.term()
                expr = BinaryOp(left=expr, op=">", right=right)
            elif self.match("PUNCT", "<="):
                right = self.term()
                expr = BinaryOp(left=expr, op="<=", right=right)
            elif self.match("PUNCT", ">="):
                right = self.term()
                expr = BinaryOp(left=expr, op=">=", right=right)
            else:
                break
        return expr

    def term(self) -> Union[BinaryOp, UnaryOp, Call, Index, Assign, NumberLit, StringLit, BoolLit, NilLit, Identifier, ListLit, DictLit, FnLit]:
        expr = self.factor()
        while True:
            if self.match("PUNCT", "+"):
                right = self.factor()
                expr = BinaryOp(left=expr, op="+", right=right)
            elif self.match("PUNCT", "-"):
                right = self.factor()
                expr = BinaryOp(left=expr, op="-", right=right)
            else:
                break
        return expr

    def factor(self) -> Union[BinaryOp, UnaryOp, Call, Index, Assign, NumberLit, StringLit, BoolLit, NilLit, Identifier, ListLit, DictLit, FnLit]:
        expr = self.unary()
        while True:
            if self.match("PUNCT", "*"):
                right = self.unary()
                expr = BinaryOp(left=expr, op="*", right=right)
            elif self.match("PUNCT", "/"):
                right = self.unary()
                expr = BinaryOp(left=expr, op="/", right=right)
            elif self.match("PUNCT", "%"):
                right = self.unary()
                expr = BinaryOp(left=expr, op="%", right=right)
            else:
                break
        return expr

    def unary(self) -> Union[BinaryOp, UnaryOp, Call, Index, Assign, NumberLit, StringLit, BoolLit, NilLit, Identifier, ListLit, DictLit, FnLit]:
        if self.match("PUNCT", "!"):
            return UnaryOp(op="!", operand=self.unary())
        if self.match("PUNCT", "-"):
            return UnaryOp(op="-", operand=self.unary())
        return self.postfix()

    def postfix(self) -> Union[BinaryOp, UnaryOp, Call, Index, Assign, NumberLit, StringLit, BoolLit, NilLit, Identifier, ListLit, DictLit, FnLit]:
        expr = self.primary()
        while True:
            if self.match("PUNCT", "("):
                args = []
                if not self.check("PUNCT", ")"):
                    while True:
                        args.append(self.expression())
                        if not self.match("PUNCT", ","):
                            break
                self.consume("PUNCT", ")", message="Expected ')' after arguments")
                expr = Call(callee=expr, args=args)
            elif self.match("PUNCT", "["):
                index = self.expression()
                self.consume("PUNCT", "]", message="Expected ']' after index")
                expr = Index(target=expr, key=index)
            else:
                break
        return expr

    def primary(self) -> Union[BinaryOp, UnaryOp, Call, Index, Assign, NumberLit, StringLit, BoolLit, NilLit, Identifier, ListLit, DictLit, FnLit]:
        if self.match("KEYWORD", "true"):
            return BoolLit(value=True)
        if self.match("KEYWORD", "false"):
            return BoolLit(value=False)
        if self.match("KEYWORD", "nil"):
            return NilLit()
        if self.match("NUMBER"):
            return NumberLit(value=self.tokens[self.pos-1].value)
        if self.match("STRING"):
            return StringLit(value=self.tokens[self.pos-1].value)
        if self.match("IDENT"):
            return Identifier(name=self.tokens[self.pos-1].value)
        if self.match("PUNCT", "("):
            expr = self.expression()
            self.consume("PUNCT", ")", message="Expected ')' after expression")
            return expr
        if self.match("PUNCT", "["):
            elements = []
            if not self.check("PUNCT", "]"):
                while True:
                    elements.append(self.expression())
                    if self.match("PUNCT", ","):
                        if self.check("PUNCT", "]"):
                            break
                    else:
                        break
            self.consume("PUNCT", "]", message="Expected ']' after list literal")
            return ListLit(items=elements)
        if self.match("PUNCT", "{"):
            pairs = []
            if not self.check("PUNCT", "}"):
                while True:
                    key = self.expression()
                    self.consume("PUNCT", ":", message="Expected ':' in dict literal")
                    value = self.expression()
                    pairs.append((key, value))
                    if self.match("PUNCT", ","):
                        if self.check("PUNCT", "}"):
                            break
                    else:
                        break
            self.consume("PUNCT", "}", message="Expected '}' after dict literal")
            return DictLit(pairs=pairs)
        if self.match("KEYWORD", "fn"):
            self.consume("PUNCT", "(", message="Expected '(' after 'fn'")
            params = self.params()
            self.consume("PUNCT", ")", message="Expected ')' after params")
            body = self.block()
            return FnLit(params=params, body=body)
        
        raise ParseError(f"Unexpected token: {self.peek().kind} {self.peek().value}", self.peek().line, self.peek().col)
