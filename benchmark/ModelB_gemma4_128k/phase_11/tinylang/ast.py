from dataclasses import dataclass
from typing import Union, Any

@dataclass
class Expr:
    line: int
    col: int

@dataclass
class Stmt:
    line: int
    col: int

@dataclass
class Program(Stmt):
    stmts: list[Stmt]
    # line and col for Program might not be very meaningful, but let's keep it for consistency
    def __init__(self, stmts: list[Stmt], line: int = 1, col: int = 1):
        super().__init__(line, col)
        self.stmts = stmts

@dataclass
class LetStmt(Stmt):
    name: str
    value: Expr

@dataclass
class IfStmt(Stmt):
    cond: Expr
    then_block: 'Block'
    else_block: Union['Block', None]

@dataclass
class WhileStmt(Stmt):
    cond: Expr
    body: 'Block'

@dataclass
class ForStmt(Stmt):
    names: list[str]
    iterable: Expr
    body: 'Block'

@dataclass
class FnDecl(Stmt):
    name: str
    params: list[str]
    body: 'Block'

@dataclass
class ReturnStmt(Stmt):
    value: Union[Expr, None]

@dataclass
class BreakStmt(Stmt):
    pass

@dataclass
class ContinueStmt(Stmt):
    pass

@dataclass
class Block(Stmt):
    stmts: list[Stmt]

@dataclass
class ExprStmt(Stmt):
    expr: Expr

@dataclass
class NumberLit(Expr):
    value: float

@dataclass
class StringLit(Expr):
    value: str

@dataclass
class BoolLit(Expr):
    value: bool

@dataclass
class NilLit(Expr):
    pass

@dataclass
class Identifier(Expr):
    name: str

@dataclass
class ListLit(Expr):
    items: list[Expr]

@dataclass
class DictLit(Expr):
    pairs: list[tuple[Expr, Expr]]

@dataclass
class FnLit(Expr):
    params: list[str]
    body: 'Block'

@dataclass
class BinaryOp(Expr):
    op: str
    left: Expr
    right: Expr

@dataclass
class UnaryOp(Expr):
    op: str
    operand: Expr

@dataclass
class Call(Expr):
    callee: Expr
    args: list[Expr]

@dataclass
class Index(Expr):
    target: Expr
    key: Expr

@dataclass
class Assign(Expr):
    target: Union[Identifier, Index]
    value: Expr
