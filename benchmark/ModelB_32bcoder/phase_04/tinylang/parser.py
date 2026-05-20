from tinylang.lexer import tokenize
from tinylang.ast import *
from typing import List, Optional, Union

class ParseError(Exception):
    def __init__(self, message: str, token):
        self.message = message
        self.token = token
        super().__init__(message)

class Parser:
    def __init__(self, tokens: List):
        self.tokens = tokens
        self.current = 0

    def parse(self) -> Program:
        stmts = []
        while not self.is_at_end():
            stmts.append(self.statement())
        return Program(stmts)

    def statement(self) -> Stmt:
        if self.match('LET'):
            return self.let_statement()
        elif self.match('IF'):
            return self.if_statement()
        elif self.match('WHILE'):
            return self.while_statement()
        elif self.match('FOR'):
            return self.for_statement()
        elif self.match('FN'):
            return self.fn_decl()
        elif self.match('RETURN'):
            return self.return_statement()
        elif self.match('BREAK'):
            return self.break_statement()
        elif self.match('CONTINUE'):
            return self.continue_statement()
        elif self.match('{'):
            return self.block()
        else:
            return self.expr_statement()

    def let_statement(self) -> LetStmt:
        name = self.consume('IDENTIFIER', 'Expect variable name.')
        self.consume('=', 'Expect = after variable name.')
        value = self.expression()
        self.consume(';', 'Expect ; after variable declaration.')
        return LetStmt(name.lexeme, value)

    def if_statement(self) -> IfStmt:
        self.consume('(', 'Expect ( after if.')
        cond = self.expression()
        self.consume(')', 'Expect ) after if condition.')
        then_block = self.block()
        else_block = None
        if self.match('ELSE'):
            if self.peek().type == 'IF':
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
        if self.peek().type == 'IDENTIFIER':
            names.append(self.advance().lexeme)
            if self.peek().type == ',':
                self.advance()
                if self.peek().type == 'IDENTIFIER':
                    names.append(self.advance().lexeme)
        self.consume('IN', 'Expect IN after for loop variable.')
        iterable = self.expression()
        self.consume(')', 'Expect ) after for loop iterable.')
        body = self.block()
        return ForStmt(names, iterable, body)

    def fn_decl(self) -> FnDecl:
        name = self.consume('IDENTIFIER', 'Expect function name.')
        self.consume('(', 'Expect ( after function name.')
        params = []
        if not self.check(')'):
            params.append(self.consume('IDENTIFIER', 'Expect parameter name.').lexeme)
            while self.match(','):
                params.append(self.consume('IDENTIFIER', 'Expect parameter name.').lexeme)
        self.consume(')', 'Expect ) after parameters.')
        body = self.block()
        return FnDecl(name.lexeme, params, body)

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

    def block(self) -> Block:
        stmts = []
        while not self.check('}') and not self.is_at_end():
            stmts.append(self.statement())
        self.consume('}', 'Expect } after block.')
        return Block(stmts)

    def expr_statement(self) -> ExprStmt:
        expr = self.expression()
        self.consume(';', 'Expect ; after expression.')
        return ExprStmt(expr)

    def expression(self) -> Expr:
        return self.assignment()

    def assignment(self) -> Expr:
        expr = self.logic_or()
        if self.match('='):
            target = expr
            value = self.assignment()
            if isinstance(target, Identifier):
                return Assign(target, value)
            elif isinstance(target, Index):
                return Assign(target, value)
            else:
                raise ParseError('Invalid assignment target.', self.peek())
        return expr

    def logic_or(self) -> Expr:
        expr = self.logic_and()
        while self.match('||'):
            right = self.logic_and()
            expr = BinaryOp('||', expr, right)
        return expr

    def logic_and(self) -> Expr:
        expr = self.equality()
        while self.match('&&'):
            right = self.equality()
            expr = BinaryOp('&&', expr, right)
        return expr

    def equality(self) -> Expr:
        expr = self.comparison()
        while self.match('==', '!='):
            operator = self.previous()
            right = self.comparison()
            expr = BinaryOp(operator.lexeme, expr, right)
        return expr

    def comparison(self) -> Expr:
        expr = self.term()
        while self.match('<', '>', '<=', '>='):
            operator = self.previous()
            right = self.term()
            expr = BinaryOp(operator.lexeme, expr, right)
        return expr

    def term(self) -> Expr:
        expr = self.factor()
        while self.match('+', '-'):
            operator = self.previous()
            right = self.factor()
            expr = BinaryOp(operator.lexeme, expr, right)
        return expr

    def factor(self) -> Expr:
        expr = self.unary()
        while self.match('*', '/', '%'):
            operator = self.previous()
            right = self.unary()
            expr = BinaryOp(operator.lexeme, expr, right)
        return expr

    def unary(self) -> Expr:
        if self.match('!', '-'):
            operator = self.previous()
            operand = self.unary()
            return UnaryOp(operator.lexeme, operand)
        return self.call()

    def call(self) -> Expr:
        expr = self.primary()
        while True:
            if self.match('('):
                expr = self.finish_call(expr)
            elif self.match('['):
                key = self.expression()
                self.consume(']', 'Expect ] after index.')
                expr = Index(expr, key)
            else:
                break
        return expr

    def finish_call(self, callee: Expr) -> Expr:
        args = []
        if not self.check(')'):
            args.append(self.expression())
            while self.match(','):
                args.append(self.expression())
        self.consume(')', 'Expect ) after arguments.')
        return Call(callee, args)

    def primary(self) -> Expr:
        if self.match('NUMBER'):
            return NumberLit(float(self.previous().lexeme))
        elif self.match('STRING'):
            return StringLit(self.previous().lexeme)
        elif self.match('TRUE'):
            return BoolLit(True)
        elif self.match('FALSE'):
            return BoolLit(False)
        elif self.match('NIL'):
            return NilLit()
        elif self.match('IDENTIFIER'):
            return Identifier(self.previous().lexeme)
        elif self.match('('):
            expr = self.expression()
            self.consume(')', 'Expect ) after expression.')
            return expr
        elif self.match('FN'):
            self.consume('(', 'Expect ( after function name.')
            params = []
            if not self.check(')'):
                params.append(self.consume('IDENTIFIER', 'Expect parameter name.').lexeme)
                while self.match(','):
                    params.append(self.consume('IDENTIFIER', 'Expect parameter name.').lexeme)
            self.consume(')', 'Expect ) after parameters.')
            body = self.block()
            return FnLit(params, body)
        elif self.match('['):
            items = []
            if not self.check(']'):
                items.append(self.expression())
                while self.match(','):
                    items.append(self.expression())
            self.consume(']', 'Expect ] after list items.')
            return ListLit(items)
        elif self.match('{'):
            pairs = []
            if not self.check('}'):
                key = self.expression()
                self.consume(':', 'Expect : after key.')
                value = self.expression()
                pairs.append((key, value))
                while self.match(','):
                    key = self.expression()
                    self.consume(':', 'Expect : after key.')
                    value = self.expression()
                    pairs.append((key, value))
            self.consume('}', 'Expect } after dict pairs.')
            return DictLit(pairs)
        else:
            raise ParseError('Expect expression.', self.peek())

    def match(self, *types: str) -> bool:
        for type in types:
            if self.check(type):
                self.advance()
                return True
        return False

    def consume(self, type: str, message: str) -> Token:
        if self.check(type):
            return self.advance()
        raise ParseError(message, self.peek())

    def check(self, type: str) -> bool:
        if self.is_at_end():
            return False
        return self.peek().type == type

    def advance(self) -> Token:
        if not self.is_at_end():
            self.current += 1
        return self.previous()

    def is_at_end(self) -> bool:
        return self.peek().type == 'EOF'

    def peek(self) -> Token:
        return self.tokens[self.current]

    def previous(self) -> Token:
        return self.tokens[self.current - 1]

def parse(source_or_tokens) -> Program:
    if isinstance(source_or_tokens, str):
        tokens = tokenize(source_or_tokens)
    else:
        tokens = source_or_tokens
    parser = Parser(tokens)
    return parser.parse()
