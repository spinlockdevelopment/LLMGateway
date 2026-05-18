from dataclasses import dataclass
from typing import List, Optional, Union

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
    name: str
    value: 'Expression'

@dataclass
class Block(Statement):
    statements: List[Statement]

@dataclass
class Expression:
    pass

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