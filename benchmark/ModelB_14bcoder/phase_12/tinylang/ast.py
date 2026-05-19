from dataclasses import dataclass
from typing import Any, List, Dict, Optional

@dataclass
class Token:
    type: str
    value: Any
    line: int
    column: int

@dataclass
class Program:
    statements: List[Any]

@dataclass
class LetStmt:
    name: str
    value: Any
    line: int
    column: int

@dataclass
class IfStmt:
    condition: Any
    then_block: Any
    else_block: Optional[Any] = None
    line: int
    column: int

@dataclass
class WhileStmt:
    condition: Any
    block: Any
    line: int
    column: int

@dataclass
class ForStmt:
    var1: str
    var2: Optional[str] = None
    iterable: Any
    block: Any
    line: int
    column: int

@dataclass
class FnDecl:
    name: str
    params: List[str]
    body: Any
    line: int
    column: int

@dataclass
class ReturnStmt:
    value: Optional[Any] = None
    line: int
    column: int

@dataclass
class BreakStmt:
    line: int
    column: int

@dataclass
class ContinueStmt:
    line: int
    column: int

@dataclass
class Block:
    statements: List[Any]
    line: int
    column: int

@dataclass
class ExprStmt:
    expression: Any
    line: int
    column: int

@dataclass
class Params:
    identifiers: List[str]
    line: int
    column: int

@dataclass
class Assignment:
    lvalue: Any
    value: Any
    line: int
    column: int

@dataclass
class LogicOr:
    left: Any
    right: Any
    line: int
    column: int

@dataclass
class LogicAnd:
    left: Any
    right: Any
    line: int
    column: int

@dataclass
class Equality:
    left: Any
    right: Any
    line: int
    column: int

@dataclass
class Comparison:
    left: Any
    right: Any
    line: int
    column: int

@dataclass
class Term:
    left: Any
    right: Any
    line: int
    column: int

@dataclass
class Factor:
    left: Any
    right: Any
    line: int
    column: int

@dataclass
class Unary:
    operator: str
    operand: Any
    line: int
    column: int

@dataclass
class Call:
    primary: Any
    args: List[Any]
    line: int
    column: int

@dataclass
class Primary:
    value: Any
    line: int
    column: int

@dataclass
class ListLit:
    elements: List[Any]
    line: int
    column: int

@dataclass
class DictLit:
    pairs: List[Any]
    line: int
    column: int

@dataclass
class Pair:
    key: Any
    value: Any
    line: int
    column: int

@dataclass
class FnLit:
    params: List[str]
    body: Any
    line: int
    column: int

@dataclass
class LValue:
    value: Any
    line: int
    column: int

@dataclass
class Args:
    expressions: List[Any]
    line: int
    column: int
