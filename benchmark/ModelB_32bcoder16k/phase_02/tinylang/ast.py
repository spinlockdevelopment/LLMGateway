from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Union

@dataclass
class Program:
    stmts: List['Stmt']

@dataclass
class LetStmt:
    name: str
    value: 'Expr'

@dataclass
class IfStmt:
    cond: 'Expr'
    then_block: 'Block'
    else_block: Optional['Block']

@dataclass
class WhileStmt:
    cond: 'Expr'
    body: 'Block'

@dataclass
class ForStmt:
    names: List[str]
    iterable: 'Expr'
    body: 'Block'

@dataclass
class FnDecl:
    name: str
    params: List[str]
    body: 'Block'

@dataclass
class ReturnStmt:
    value: Optional['Expr']

@dataclass
class BreakStmt:
    pass

@dataclass
class ContinueStmt:
    pass

@dataclass
class Block:
    stmts: List['Stmt']

@dataclass
class ExprStmt:
    expr: 'Expr'

@dataclass
class NumberLit:
    value: float

@dataclass
class StringLit:
    value: str

@dataclass
class BoolLit:
    value: bool

@dataclass
class NilLit:
    pass

@dataclass
class Identifier:
    name: str

@dataclass
class ListLit:
    items: List['Expr']

@dataclass
class DictLit:
    pairs: List[Tuple['Expr', 'Expr']]

@dataclass
class FnLit:
    params: List[str]
    body: 'Block'

@dataclass
class BinaryOp:
    op: str
    left: 'Expr'
    right: 'Expr'

@dataclass
class UnaryOp:
    op: str
    operand: 'Expr'

@dataclass
class Call:
    callee: 'Expr'
    args: List['Expr']

@dataclass
class Index:
    target: 'Expr'
    key: 'Expr'

@dataclass
class Assign:
    target: 'Expr'
    value: 'Expr'

Stmt = Union[LetStmt, IfStmt, WhileStmt, ForStmt, FnDecl, ReturnStmt, BreakStmt, ContinueStmt, Block, ExprStmt]
Expr = Union[NumberLit, StringLit, BoolLit, NilLit, Identifier, ListLit, DictLit, FnLit, BinaryOp, UnaryOp, Call, Index, Assign]
