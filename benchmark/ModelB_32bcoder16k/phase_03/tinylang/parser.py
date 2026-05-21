from tinylang.lexer import tokenize
from tinylang.ast import *
from typing import List, Optional, Union

class ParseError(Exception):
    def __init__(self, message: str, token: Optional['Token'] = None):
        self.message = message
        self.token = token
        super().__init__(message)

    def __str__(self):
        if self.token:
            return f"Parse error at line {self.token.line}, column {self.token.col}: {self.message}"
        return self.message

class Parser:
    def __init__(self, tokens: List['Token']):
        self.tokens = tokens
        self.current = 0

    def parse(self) -> Program:
        stmts = []
        while not self.is_at_end():
            stmts.append(self.statement())
        return Program(stmts)

    def statement(self) -> 'Stmt':
        if self.match('let'):
            return self.let_statement()
        elif self.match('if'):
            return self.if_statement()
        elif self.match('while'):
            return self.while_statement()
        elif self.match('for'):
            return self.for_statement()
        elif self.match('fn'):
            return self.fn_declaration()
        elif self.match('return'):
            return self.return_statement()
        elif self.match('break'):
            return self.break_statement()
        elif self.match('continue'):
            return self.continue_statement()
        elif self.match('{'):
            return self.block()
        else:
            return self.expr_statement()

    def let_statement(self) -> LetStmt:
        name = self.consume('IDENT', 'Expect variable name.')
        self.consume('=', 'Expect = after variable name.')
        value = self.expression()
        self.consume(';', 'Expect ; after variable initializer.')
        return LetStmt(name.text, value)

    def if_statement(self) -> IfStmt:
        self.consume('(', 'Expect ( after if.')
        cond = self.expression()
        self.consume(')', 'Expect ) after if condition.')
        then_block = self.block()
        else_block = None
        if self.match('else'):
            if self.peek().type == 'if':
                else_block = self.if_statement()
            else:
                else_block = self.block()
        return IfStmt(cond, then_block, else_block)

    def while_statement(self) -> WhileStmt:
        self.consume('(', 'Expect ( after while.')
        cond = self.expression()
        self.consume(')', 'Expect ) after while condition.')
        body = self.block()
        return WhileStmt(cond, body)

    def for_statement(self) -> ForStmt:
        self.consume('(', 'Expect ( after for.')
        names = []
        if self.peek().type == 'IDENT':
            names.append(self.advance().text)
            if self.peek().type == ',':
                self.advance()
                if self.peek().type == 'IDENT':
                    names.append(self.advance().text)
        self.consume('in', 'Expect in after for loop variable.')
        iterable = self.expression()
        self.consume(')', 'Expect ) after for loop iterable.')
        body = self.block()
        return ForStmt(names, iterable, body)

    def fn_declaration(self) -> FnDecl:
        name = self.consume('IDENT', 'Expect function name.').text
        self.consume('(', 'Expect ( after function name.')
        params = []
        if not self.check(')'):
            while True:
                if len(params) >= 255:
                    self.error(self.peek(), 'Cannot have more than 255 parameters.')
                params.append(self.consume('IDENT', 'Expect parameter name.').text)
                if not self.match(','):
                    break
        self.consume(')', 'Expect ) after parameters.')
        self.consume('{', 'Expect { before function body.')
        body = self.block()
        return FnDecl(name, params, body)

    def return_statement(self) -> ReturnStmt:
        value = None
        if not self.check(';'):
            value = self.expression()
        self.consume(';', 'Expect ; after return value.')
        return ReturnStmt(value)

    def break_statement(self) -> BreakStmt:
        self.consume(';', 'Expect ; after break.')
        return BreakStmt()

    def continue_statement(self) -> ContinueStmt:
        self.consume(';', 'Expect ; after continue.')
        return ContinueStmt()

    def expr_statement(self) -> ExprStmt:
        expr = self.expression()
        self.consume(';', 'Expect ; after expression.')
        return ExprStmt(expr)

    def block(self) -> Block:
        stmts = []
        while not self.check('}') and not self.is_at_end():
            stmts.append(self.statement())
        self.consume('}', 'Expect } after block.')
        return Block(stmts)

    def expression(self) -> 'Expr':
        return self.assignment()

    def assignment(self) -> 'Expr':
        expr = self.logic_or()
        if self.match('='):
            equals = self.previous()
            value = self.assignment()
            if isinstance(expr, Identifier):
                return Assign(expr, value)
            elif isinstance(expr, Index):
                return Assign(expr, value)
            self.error(equals, 'Invalid assignment target.')
        return expr

    def logic_or(self) -> 'Expr':
        expr = self.logic_and()
        while self.match('||'):
            operator = self.previous()
            right = self.logic_and()
            expr = BinaryOp(operator.text, expr, right)
        return expr

    def logic_and(self) -> 'Expr':
        expr = self.equality()
        while self.match('&&'):
            operator = self.previous()
            right = self.equality()
            expr = BinaryOp(operator.text, expr, right)
        return expr

    def equality(self) -> 'Expr':
        expr = self.comparison()
        while self.match('==', '!='):
            operator = self.previous()
            right = self.comparison()
            expr = BinaryOp(operator.text, expr, right)
        return expr

    def comparison(self) -> 'Expr':
        expr = self.term()
        while self.match('<', '>', '<=', '>='):
            operator = self.previous()
            right = self.term()
            expr = BinaryOp(operator.text, expr, right)
        return expr

    def term(self) -> 'Expr':
        expr = self.factor()
        while self.match('+', '-'):
            operator = self.previous()
            right = self.factor()
            expr = BinaryOp(operator.text, expr, right)
        return expr

    def factor(self) -> 'Expr':
        expr = self.unary()
        while self.match('*', '/', '%'):
            operator = self.previous()
            right = self.unary()
            expr = BinaryOp(operator.text, expr, right)
        return expr

    def unary(self) -> 'Expr':
        if self.match('!', '-'):
            operator = self.previous()
            right = self.unary()
            return UnaryOp(operator.text, right)
        return self.call()

    def call(self) -> 'Expr':
        expr = self.primary()
        while True:
            if self.match('('):
                expr = self.finish_call(expr)
            elif self.match('['):
                key = self.expression()
                self.consume(']', 'Expect ] after expression.')
                expr = Index(expr, key)
            else:
                break
        return expr

    def finish_call(self, callee: 'Expr') -> Call:
        args = []
        if not self.check(')'):
            while True:
                if len(args) >= 255:
                    self.error(self.peek(), 'Cannot have more than 255 arguments.')
                args.append(self.expression())
                if not self.match(','):
                    break
        self.consume(')', 'Expect ) after arguments.')
        return Call(callee, args)

    def primary(self) -> 'Expr':
        if self.match('NUMBER'):
            return NumberLit(float(self.previous().text))
        elif self.match('STRING'):
            return StringLit(self.previous().text[1:-1])
        elif self.match('true'):
            return BoolLit(True)
        elif self.match('false'):
            return BoolLit(False)
        elif self.match('nil'):
            return NilLit()
        elif self.match('IDENT'):
            return Identifier(self.previous().text)
        elif self.match('('):
            expr = self.expression()
            self.consume(')', 'Expect ) after expression.')
            return expr
        elif self.match('fn'):
            return self.fn_expression()
        else:
            self.error(self.peek(), 'Expect expression.')

    def fn_expression(self) -> FnLit:
        self.consume('(', 'Expect ( after fn.')
        params = []
        if not self.check(')'):
            while True:
                if len(params) >= 255:
                    self.error(self.peek(), 'Cannot have more than 255 parameters.')
                params.append(self.consume('IDENT', 'Expect parameter name.').text)
                if not self.match(','):
                    break
        self.consume(')', 'Expect ) after parameters.')
        self.consume('{', 'Expect { before function body.')
        body = self.block()
        return FnLit(params, body)

    def match(self, *types: str) -> bool:
        for type in types:
            if self.check(type):
                self.advance()
                return True
        return False

    def consume(self, type: str, message: str) -> 'Token':
        if self.check(type):
            return self.advance()
        self.error(self.peek(), message)

    def check(self, type: str) -> bool:
        if self.is_at_end():
            return False
        return self.peek().type == type

    def advance(self) -> 'Token':
        if not self.is_at_end():
            self.current += 1
        return self.previous()

    def is_at_end(self) -> bool:
        return self.peek().type == 'EOF'

    def peek(self) -> 'Token':
        return self.tokens[self.current]

    def previous(self) -> 'Token':
        return self.tokens[self.current - 1]

    def error(self, token: 'Token', message: str) -> ParseError:
        raise ParseError(message, token)

def parse(source_or_tokens: Union[str, List['Token']]) -> Program:
    if isinstance(source_or_tokens, str):
        tokens = tokenize(source_or_tokens)
    else:
        tokens = source_or_tokens
    parser = Parser(tokens)
    return parser.parse()
