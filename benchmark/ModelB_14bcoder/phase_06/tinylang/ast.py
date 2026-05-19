from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple

@dataclass
class Program:
    stmts: List[Any] = field(default_factory=list)

@dataclass
class LetStmt:
    name: str
    value: Any

@dataclass
class IfStmt:
    cond: Any
    then_block: Any
    else_block: Optional[Any] = None

@dataclass
class WhileStmt:
    cond: Any
    body: Any

@dataclass
class ForStmt:
    names: List[str]
    iterable: Any
    body: Any

@dataclass
class FnDecl:
    name: str
    params: List[str]
    body: Any

@dataclass
class ReturnStmt:
    value: Optional[Any] = None

@dataclass
class BreakStmt:
    pass

@dataclass
class ContinueStmt:
    pass

@dataclass
class Block:
    stmts: List[Any] = field(default_factory=list)

@dataclass
class ExprStmt:
    expr: Any

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
    items: List[Any] = field(default_factory=list)

@dataclass
class DictLit:
    pairs: List[Tuple[Any, Any]] = field(default_factory=list)

@dataclass
class FnLit:
    params: List[str]
    body: Any

@dataclass
class BinaryOp:
    op: str
    left: Any
    right: Any

@dataclass
class UnaryOp:
    op: str
    operand: Any

@dataclass
class Call:
    callee: Any
    args: List[Any] = field(default_factory=list)

@dataclass
class Index:
    target: Any
    key: Any

@dataclass
class Assign:
    target: Any
    value: Any
