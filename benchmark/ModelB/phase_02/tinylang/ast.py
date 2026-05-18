from dataclasses import dataclass
from typing import List, Optional

# Program node
@dataclass
class Program:
    stmts: List

# Statement nodes
@dataclass
class LetStmt:
    name: str
    value: 'Expr'

@dataclass
class IfStmt:
    cond: 'Expr'
    then_block: 'Block'
    else_block: Optional['Block'] = None

@dataclass
class WhileStmt:
    cond: 'Expr'
    body: 'Block'

@dataclass
class ForStmt:
    names: List[str]  # Can be 1 or 2 names (index, value)
    iterable: 'Expr'
    body: 'Block'

@dataclass
class FnDecl:
    name: str
    params: List[str]
    body: 'Block'

@dataclass
class ReturnStmt:
    value: Optional['Expr'] = None

@dataclass
class BreakStmt:
    pass

@dataclass
class ContinueStmt:
    pass

@dataclass
class Block:
    stmts: List

@dataclass
class ExprStmt:
    expr: 'Expr'

# Expression nodes
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
    pairs: List[tuple['Expr', 'Expr']]  # List of (key, value) pairs

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
    target: 'Expr'  # Identifier or Index
    value: 'Expr'