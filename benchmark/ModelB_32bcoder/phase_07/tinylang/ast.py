from dataclasses import dataclass
from typing import Any, Dict, List, Optional

@dataclass
class Token:
    type: str
    value: Any
    line: int
    col: int

@dataclass
class Program:
    statements: List['Statement']

@dataclass
class LetStmt:
    name: str
    value: 'Expression'

@dataclass
class IfStmt:
    condition: 'Expression'
    then_block: 'Block'
    else_block: Optional['Block']

@dataclass
class WhileStmt:
    condition: 'Expression'
    block: 'Block'

@dataclass
class ForStmt:
    var_name: str
    index_name: Optional[str]
    iterable: 'Expression'
    block: 'Block'

@dataclass
class FnDecl:
    name: str
    params: List[str]
    body: 'Block'

@dataclass
class ReturnStmt:
    value: Optional['Expression']

@dataclass
class BreakStmt:
    pass

@dataclass
class ContinueStmt:
    pass

@dataclass
class Block:
    statements: List['Statement']

@dataclass
class ExprStmt:
    expression: 'Expression'

@dataclass
class Assignment:
    lvalue: 'LValue'
    value: 'Expression'

@dataclass
class LogicOr:
    left: 'Expression'
    right: 'Expression'

@dataclass
class LogicAnd:
    left: 'Expression'
    right: 'Expression'

@dataclass
class Equality:
    left: 'Expression'
    right: 'Expression'
    operator: str

@dataclass
class Comparison:
    left: 'Expression'
    right: 'Expression'
    operator: str

@dataclass
class Term:
    left: 'Expression'
    right: 'Expression'
    operator: str

@dataclass
class Factor:
    left: 'Expression'
    right: 'Expression'
    operator: str

@dataclass
class Unary:
    operator: str
    operand: 'Expression'

@dataclass
class Call:
    function: 'Expression'
    args: List['Expression']

@dataclass
class Primary:
    value: Any

@dataclass
class ListLit:
    elements: List['Expression']

@dataclass
class DictLit:
    pairs: List['Pair']

@dataclass
class Pair:
    key: 'Expression'
    value: 'Expression'

@dataclass
class FnLit:
    params: List[str]
    body: 'Block'

@dataclass
class LValue:
    name: str

Statement = LetStmt | IfStmt | WhileStmt | ForStmt | FnDecl | ReturnStmt | BreakStmt | ContinueStmt | Block | ExprStmt
Expression = Assignment | LogicOr | LogicAnd | Equality | Comparison | Term | Factor | Unary | Call | Primary | ListLit | DictLit | FnLit
