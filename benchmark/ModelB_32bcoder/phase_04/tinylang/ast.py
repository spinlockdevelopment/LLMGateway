from dataclasses import dataclass, field
from typing import List, Optional
from tinylang.errors import LexError

@dataclass
class Token:
    type: str
    value: str
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
class Block:
    statements: List['Statement']

@dataclass
class Identifier:
    name: str

@dataclass
class Assign:
    target: Identifier
    value: 'Expression'

@dataclass
class ExpressionStmt:
    expression: 'Expression'

@dataclass
class PrintStmt:
    args: List['Expression']

@dataclass
class Number:
    value: float

Statement = LetStmt | Block | ExpressionStmt | PrintStmt
Expression = Identifier | Number | Assign

@dataclass
class BinOp:
    operator: str
    left: 'Expression'
    right: 'Expression'

Expression = Expression | BinOp

@dataclass
class UnaryOp:
    operator: str
    operand: 'Expression'

Expression = Expression | UnaryOp

@dataclass
class Call:
    callee: 'Expression'
    args: List['Expression']

Expression = Expression | Call

@dataclass
class Index:
    collection: 'Expression'
    index: 'Expression'

Expression = Expression | Index

@dataclass
class DictLit:
    pairs: List['Pair']

Expression = Expression | DictLit

@dataclass
class ListLit:
    elements: List['Expression']

Expression = Expression | ListLit

@dataclass
class Pair:
    key: 'Expression'
    value: 'Expression'

@dataclass
class FnLit:
    params: List[str]
    body: Block

Expression = Expression | FnLit

@dataclass
class ReturnStmt:
    value: Optional['Expression']

Statement = Statement | ReturnStmt

@dataclass
class IfStmt:
    condition: 'Expression'
    then_branch: Block
    else_branch: Optional[Block]

Statement = Statement | IfStmt

@dataclass
class WhileStmt:
    condition: 'Expression'
    body: Block

Statement = Statement | WhileStmt

@dataclass
class ForStmt:
    key: Optional[Identifier]
    value: Optional[Identifier]
    iterable: 'Expression'
    body: Block

Statement = Statement | ForStmt

@dataclass
class BreakStmt:
    pass

Statement = Statement | BreakStmt

@dataclass
class ContinueStmt:
    pass

Statement = Statement | ContinueStmt
