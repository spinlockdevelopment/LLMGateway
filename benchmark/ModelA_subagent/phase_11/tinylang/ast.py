"""AST node definitions for tinylang.

Each node is a small dataclass. Tests inspect ``type(node).__name__`` and
attribute names, so the exact names and fields here are part of the
public contract — see ``spec/phase_02_parser.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Program / statements
# ---------------------------------------------------------------------------


@dataclass
class Program:
    stmts: list = field(default_factory=list)


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
    names: list
    iterable: Any
    body: Any


@dataclass
class FnDecl:
    name: str
    params: list
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
    stmts: list = field(default_factory=list)


@dataclass
class ExprStmt:
    expr: Any


# ---------------------------------------------------------------------------
# Expressions
# ---------------------------------------------------------------------------


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
    items: list = field(default_factory=list)


@dataclass
class DictLit:
    pairs: list = field(default_factory=list)  # list[tuple[Expr, Expr]]


@dataclass
class FnLit:
    params: list
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
    args: list


@dataclass
class Index:
    target: Any
    key: Any


@dataclass
class Assign:
    target: Any
    value: Any
