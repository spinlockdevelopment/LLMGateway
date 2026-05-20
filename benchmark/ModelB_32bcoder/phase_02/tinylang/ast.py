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
    def __init__(self, name: str, params: List[str], body: Block):
        self.name = name
        self.params = params
        self.body = body

    def __repr__(self):
        return f'FnDecl(name={self.name}, params={self.params}, body={self.body})'

@dataclass
class ReturnStmt:
    value: Optional[Expr]

    def __repr__(self):
        return f'ReturnStmt(value={self.value})'

@dataclass
class BreakStmt:
    pass

    def __repr__(self):
        return 'BreakStmt()'

@dataclass
class ContinueStmt:
    pass

    def __repr__(self):
        return 'ContinueStmt()'

@dataclass
class Block:
    stmts: List[Stmt]

    def __repr__(self):
        return f'Block(stmts={self.stmts})'

@dataclass
class ExprStmt:
    expr: Expr

    def __repr__(self):
        return f'ExprStmt(expr={self.expr})'

@dataclass
class NumberLit:
    value: float

    def __repr__(self):
        return f'NumberLit(value={self.value})'

@dataclass
class StringLit:
    value: str

    def __repr__(self):
        return f'StringLit(value={self.value})'

@dataclass
class BoolLit:
    value: bool

    def __repr__(self):
        return f'BoolLit(value={self.value})'

@dataclass
class NilLit:
    pass

    def __repr__(self):
        return 'NilLit()'

@dataclass
class Identifier:
    name: str

    def __repr__(self):
        return f'Identifier(name={self.name})'

@dataclass
class ListLit:
    items: List[Expr]

    def __repr__(self):
        return f'ListLit(items={self.items})'

@dataclass
class DictLit:
    pairs: List[Tuple[Expr, Expr]]

    def __repr__(self):
        return f'DictLit(pairs={self.pairs})'

@dataclass
class FnLit:
    params: List[str]
    body: Block

    def __repr__(self):
        return f'FnLit(params={self.params}, body={self.body})'

@dataclass
class BinaryOp:
    op: str
    left: Expr
    right: Expr

    def __repr__(self):
        return f'BinaryOp(op={self.op}, left={self.left}, right={self.right})'

@dataclass
class UnaryOp:
    op: str
    operand: Expr

    def __repr__(self):
        return f'UnaryOp(op={self.op}, operand={self.operand})'

@dataclass
class Call:
    callee: Expr
    args: List[Expr]

    def __repr__(self):
        return f'Call(callee={self.callee}, args={self.args})'

@dataclass
class Index:
    target: Expr
    key: Expr

    def __repr__(self):
        return f'Index(target={self.target}, key={self.key})'

@dataclass
class Assign:
    target: Expr
    value: Expr

    def __repr__(self):
        return f'Assign(target={self.target}, value={self.value})'

Stmt = Union[LetStmt, IfStmt, WhileStmt, ForStmt, FnDecl, ReturnStmt, BreakStmt, ContinueStmt, Block, ExprStmt]
Expr = Union[NumberLit, StringLit, BoolLit, NilLit, Identifier, ListLit, DictLit, FnLit, BinaryOp, UnaryOp, Call, Index, Assign]