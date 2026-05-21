from dataclasses import dataclass, field
from typing import List, Optional, Union

class Expression:
    pass

@dataclass
class Token:
    type: str
    lexeme: str
    literal: Optional[Union[int, float, str, bool, None]]
    line: int

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
class BinaryExpression(Expression):
    left: 'Expression'
    operator: str
    right: 'Expression'

@dataclass
class UnaryExpression(Expression):
    operator: str
    operand: 'Expression'

@dataclass
class Literal(Expression):
    value: Union[int, float, str, bool, None]

@dataclass
class CallExpression(Expression):
    callee: 'Expression'
    arguments: List['Expression']

@dataclass
class Identifier(Expression):
    name: str

Expression = Union[BinaryExpression, UnaryExpression, Literal, CallExpression, Identifier]
