from dataclasses import dataclass
from typing import List, Optional, Union

@dataclass
class Expression:
    pass

@dataclass
class Program:
    statements: List['Statement']

@dataclass
class Statement:
    pass

@dataclass
class ExpressionStatement(Statement):
    expression: 'Expression'

@dataclass
class LetStmt(Statement):
    name: str
    value: 'Expression'

@dataclass
class Assign(Statement):
    target: 'Expression'
    value: 'Expression'

@dataclass
class Block(Statement):
    statements: List[Statement]

@dataclass
class IfStmt(Statement):
    condition: Expression
    then_branch: Statement
    else_branch: Optional[Statement]

@dataclass
class WhileStmt(Statement):
    condition: Expression
    body: Statement

@dataclass
class BreakStmt(Statement):
    pass

@dataclass
class ContinueStmt(Statement):
    pass

@dataclass
class ReturnStmt(Statement):
    value: Optional['Expression']

@dataclass
class FnDecl(Statement):
    name: str
    parameters: List[str]
    body: 'Block'

@dataclass
class FnLit(Expression):
    parameters: List[str]
    body: 'Block'

@dataclass
class ListLit(Expression):
    elements: List[Expression]

@dataclass
class Index(Expression):
    target: Expression
    index: Expression

@dataclass
class BinaryExpression(Expression):
    left: Expression
    operator: str
    right: Expression

@dataclass
class UnaryExpression(Expression):
    operator: str
    right: Expression

@dataclass
class LiteralExpression(Expression):
    value: Union[int, float, str, bool, None]

@dataclass
class IdentifierExpression(Expression):
    name: str

@dataclass
class CallExpression(Expression):
    callee: Expression
    arguments: List[Expression]