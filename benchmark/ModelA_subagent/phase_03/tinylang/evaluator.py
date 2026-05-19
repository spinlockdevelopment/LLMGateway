"""Tree-walking evaluator for tinylang — Phase 3 scope.

Phase 3 only covers expression statements with numbers, strings, booleans,
nil, arithmetic, comparisons, logical operators, and the ``print`` built-in.
Variables, control flow, and user-defined functions arrive in later phases.

Public surface (per ``spec/overall_brief.md`` §7):

    from tinylang.evaluator import run
    run(source: str) -> str
"""

from __future__ import annotations

from typing import Any

from .ast import (
    BinaryOp,
    BoolLit,
    Call,
    ExprStmt,
    Identifier,
    NilLit,
    NumberLit,
    Program,
    StringLit,
    UnaryOp,
)
from .builtins import make_builtins
from .parser import parse


# --------------------------------------------------------------------------- #
# Truthiness                                                                  #
# --------------------------------------------------------------------------- #


def is_truthy(value: Any) -> bool:
    """tinylang truthiness: ``nil``, ``false`` and ``0`` are falsy."""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return True


# --------------------------------------------------------------------------- #
# Evaluator                                                                   #
# --------------------------------------------------------------------------- #


class _Evaluator:
    def __init__(self) -> None:
        self.output: list[str] = []
        self.builtins = make_builtins(self.output)

    # --------------------------------------------------------------- program

    def run_program(self, program: Program) -> str:
        for stmt in program.stmts:
            self.exec_stmt(stmt)
        return "".join(self.output)

    # ------------------------------------------------------------ statements

    def exec_stmt(self, stmt: Any) -> None:
        if isinstance(stmt, ExprStmt):
            self.eval_expr(stmt.expr)
            return
        # Phase 3: anything else is out of scope. Later phases extend this.
        raise Exception(
            f"unsupported statement {type(stmt).__name__} in phase 3"
        )

    # ----------------------------------------------------------- expressions

    def eval_expr(self, expr: Any) -> Any:
        if isinstance(expr, NumberLit):
            return float(expr.value)
        if isinstance(expr, StringLit):
            return expr.value
        if isinstance(expr, BoolLit):
            return bool(expr.value)
        if isinstance(expr, NilLit):
            return None
        if isinstance(expr, Identifier):
            return self.lookup_name(expr.name)
        if isinstance(expr, UnaryOp):
            return self.eval_unary(expr)
        if isinstance(expr, BinaryOp):
            return self.eval_binary(expr)
        if isinstance(expr, Call):
            return self.eval_call(expr)
        raise Exception(f"unsupported expression {type(expr).__name__}")

    # ---------------------------------------------------------- name lookup

    def lookup_name(self, name: str) -> Any:
        if name in self.builtins:
            return self.builtins[name]
        raise Exception(f"undefined name '{name}'")

    # -------------------------------------------------------------- unary op

    def eval_unary(self, node: UnaryOp) -> Any:
        if node.op == "-":
            value = self.eval_expr(node.operand)
            if not isinstance(value, float) or isinstance(value, bool):
                raise Exception(
                    f"unary '-' expects a number, got {_type_name(value)}"
                )
            return -value
        if node.op == "!":
            return not is_truthy(self.eval_expr(node.operand))
        raise Exception(f"unknown unary operator '{node.op}'")

    # ------------------------------------------------------------ binary op

    def eval_binary(self, node: BinaryOp) -> Any:
        op = node.op

        # Short-circuit logical operators — evaluate RHS only when needed,
        # and return the operand value (JS semantics), not a coerced bool.
        if op == "&&":
            left = self.eval_expr(node.left)
            if not is_truthy(left):
                return left
            return self.eval_expr(node.right)
        if op == "||":
            left = self.eval_expr(node.left)
            if is_truthy(left):
                return left
            return self.eval_expr(node.right)

        left = self.eval_expr(node.left)
        right = self.eval_expr(node.right)

        if op == "+":
            return self._op_plus(left, right)
        if op == "-":
            _check_numbers(op, left, right)
            return left - right
        if op == "*":
            _check_numbers(op, left, right)
            return left * right
        if op == "/":
            _check_numbers(op, left, right)
            if right == 0:
                raise Exception("division by zero")
            return left / right
        if op == "%":
            _check_numbers(op, left, right)
            if right == 0:
                raise Exception("modulo by zero")
            return left % right

        if op == "==":
            return _equal(left, right)
        if op == "!=":
            return not _equal(left, right)

        if op in ("<", ">", "<=", ">="):
            return self._op_compare(op, left, right)

        raise Exception(f"unknown binary operator '{op}'")

    @staticmethod
    def _op_plus(left: Any, right: Any) -> Any:
        # Strings concat; numbers add. No silent coercion.
        if isinstance(left, str) and isinstance(right, str):
            return left + right
        if (
            isinstance(left, float)
            and not isinstance(left, bool)
            and isinstance(right, float)
            and not isinstance(right, bool)
        ):
            return left + right
        raise Exception(
            f"'+' requires two numbers or two strings, "
            f"got {_type_name(left)} and {_type_name(right)}"
        )

    @staticmethod
    def _op_compare(op: str, left: Any, right: Any) -> bool:
        # Order comparisons need same type, numbers or strings.
        if (
            isinstance(left, float)
            and not isinstance(left, bool)
            and isinstance(right, float)
            and not isinstance(right, bool)
        ) or (isinstance(left, str) and isinstance(right, str)):
            if op == "<":
                return left < right
            if op == ">":
                return left > right
            if op == "<=":
                return left <= right
            if op == ">=":
                return left >= right
        raise Exception(
            f"'{op}' requires two numbers or two strings, "
            f"got {_type_name(left)} and {_type_name(right)}"
        )

    # ----------------------------------------------------------------- calls

    def eval_call(self, node: Call) -> Any:
        callee = self.eval_expr(node.callee)
        args = [self.eval_expr(a) for a in node.args]
        if not callable(callee):
            raise Exception(f"cannot call {_type_name(callee)}")
        return callee(*args)


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _type_name(value: Any) -> str:
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, float):
        return "number"
    if isinstance(value, int):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    if callable(value):
        return "function"
    return type(value).__name__


def _equal(left: Any, right: Any) -> bool:
    """tinylang ``==``: equal only when same type and same value.

    Cross-type compares are allowed (and return ``False``); the only subtlety
    is that Python's ``bool`` is a subclass of ``int``/``float``, so we have
    to short-circuit that ourselves to avoid ``True == 1.0`` reporting true.
    """
    left_bool = isinstance(left, bool)
    right_bool = isinstance(right, bool)
    if left_bool != right_bool:
        return False
    if left is None or right is None:
        return left is None and right is None
    if isinstance(left, str) != isinstance(right, str):
        return False
    # Both numbers (and not bools) or both strings or both bools: direct eq.
    return left == right


def _check_numbers(op: str, left: Any, right: Any) -> None:
    if (
        not isinstance(left, float)
        or isinstance(left, bool)
        or not isinstance(right, float)
        or isinstance(right, bool)
    ):
        raise Exception(
            f"'{op}' requires two numbers, "
            f"got {_type_name(left)} and {_type_name(right)}"
        )


# --------------------------------------------------------------------------- #
# Public entry point                                                          #
# --------------------------------------------------------------------------- #


def run(source: str) -> str:
    """Parse and execute ``source``; return everything ``print`` wrote."""
    program = parse(source)
    evaluator = _Evaluator()
    return evaluator.run_program(program)
