from dataclasses import dataclass
from typing import List, Optional

# Program node
@dataclass
class Program:
    stmts: List[object]

# Statement nodes
@dataclass
class LetStmt:
    name: str
    value: object

@dataclass
class IfStmt:
    cond: object
    then_block: object
    else_block: Optional[object] = None

@dataclass
class WhileStmt:
    cond: object
    body: object

@dataclass
class ForStmt:
    names: List[str]
    iterable: object
    body: object

@dataclass
class FnDecl:
    name: str
    params: List[str]
    body: object

@dataclass
class ReturnStmt:
    value: Optional[object] = None

@dataclass
class BreakStmt:
    pass

@dataclass
class ContinueStmt:
    pass

@dataclass
class Block:
    stmts: List[object]

@dataclass
class ExprStmt:
    expr: object

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
    items: List[object]

@dataclass
class DictLit:
    pairs: List[tuple[object, object]]

@dataclass
class FnLit:
    params: List[str]
    body: object

@dataclass
class BinaryOp:
    op: str
    left: object
    right: object

@dataclass
class UnaryOp:
    op: str
    operand: object

@dataclass
class Call:
    callee: object
    args: List[object]

@dataclass
class Index:
    target: object
    key: object

@dataclass
class Assign:
    target: object
    value: object