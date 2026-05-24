from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Union

@dataclass
class Expr:
    pass

@dataclass
class Statement:
    pass

@dataclass
class Program:
    stmts: list[Statement]

@dataclass
class LetStmt(Statement):
    name: str
    value: Expr

@dataclass
class IfStmt(Statement):
    cond: Expr
    then_block: Block
    else_block: Union[Block, IfStmt, None]

@dataclass
class WhileStmt(Statement):
    cond: Expr
    body: Block

@dataclass
class ForStmt(Statement):
    names: list[str]
    iterable: Expr
    body: Block

@dataclass
class FnDecl(Statement):
    name: str
    params: list[str]
    body: Block

@dataclass
class ReturnStmt(Statement):
    value: Union[Expr, None]

@dataclass
class BreakStmt(Statement):
    pass

@dataclass
class ContinueStmt(Statement):
    pass

@dataclass
class Block(Statement):
    stmts: list[Statement]

@dataclass
class ExprStmt(Statement):
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
    args: list[Expr]

@dataclass
class Index(Expr):
    target: Expr
    key: Expr

@dataclass
class Assign(Expr):
    target: Union[Identifier, Index]
    value: Expr
