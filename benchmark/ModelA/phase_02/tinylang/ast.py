from dataclasses import dataclass
from typing import List, Optional, Union, Tuple


# Base classes
@dataclass
class Stmt:
    pass


@dataclass
class Expr:
    pass


# Program
@dataclass
class Program:
    stmts: List[Stmt]


# Statements
@dataclass
class LetStmt(Stmt):
    name: str
    value: Expr


@dataclass
class IfStmt(Stmt):
    cond: Expr
    then_block: 'Block'
    else_block: Optional['Block']


@dataclass
class WhileStmt(Stmt):
    cond: Expr
    body: 'Block'


@dataclass
class ForStmt(Stmt):
    names: List[str]
    iterable: Expr
    body: 'Block'


@dataclass
class FnDecl(Stmt):
    name: str
    params: List[str]
    body: 'Block'


@dataclass
class ReturnStmt(Stmt):
    value: Optional[Expr]


@dataclass
class BreakStmt(Stmt):
    pass


@dataclass
class ContinueStmt(Stmt):
    pass


@dataclass
class Block(Stmt):
    stmts: List[Stmt]


@dataclass
class ExprStmt(Stmt):
    expr: Expr


# Expressions
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
    items: List[Expr]


@dataclass
class DictLit(Expr):
    pairs: List[Tuple[Expr, Expr]]


@dataclass
class FnLit(Expr):
    params: List[str]
    body: Block


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
    args: List[Expr]


@dataclass
class Index(Expr):
    target: Expr
    key: Expr


@dataclass
class Assign(Expr):
    target: Expr
    value: Expr