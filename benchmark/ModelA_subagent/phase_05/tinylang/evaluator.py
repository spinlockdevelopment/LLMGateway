"""Tree-walking evaluator for tinylang — phases 1-5.

Phase 3 covered expression statements (numbers, strings, booleans, nil,
arithmetic, comparisons, logical ops, ``print``). Phase 4 added:

* ``let`` declarations in a real lexical :class:`Environment`.
* Re-assignment via the ``Assign`` AST node (``x = expr``), which must hit
  an existing binding (no silent globals).
* Block statements that open a fresh child scope and discard their bindings
  on exit.
* Identifier lookup that walks the scope chain, falling back to built-ins.

Phase 5 adds control flow:

* ``if`` / ``else`` (and ``else if`` chains, which the parser desugars to
  nested ``IfStmt`` nodes).
* ``while`` loops with block-scoped bodies.
* ``break`` and ``continue``, implemented via private signal exceptions
  caught by the nearest enclosing ``while``. Using these outside a loop
  is a runtime error.

Public surface (per ``spec/overall_brief.md`` §7):

    from tinylang.evaluator import run
    run(source: str) -> str
"""

from __future__ import annotations

from typing import Any

from .ast import (
    Assign,
    BinaryOp,
    Block,
    BoolLit,
    BreakStmt,
    Call,
    ContinueStmt,
    ExprStmt,
    Identifier,
    IfStmt,
    LetStmt,
    NilLit,
    NumberLit,
    Program,
    StringLit,
    UnaryOp,
    WhileStmt,
)
from .builtins import make_builtins
from .environment import Environment
from .parser import parse


# --------------------------------------------------------------------------- #
# Loop signals (private to this module)                                       #
# --------------------------------------------------------------------------- #


class _BreakSignal(Exception):
    """Raised by ``break``; caught only by the nearest enclosing ``while``."""


class _ContinueSignal(Exception):
    """Raised by ``continue``; caught only by the nearest enclosing ``while``."""


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
        # The global environment holds user-defined ``let`` bindings.
        # Built-ins live in a *separate* dict and are consulted only when an
        # identifier is not found in any user scope, so user code may shadow
        # ``print`` with ``let print = ...`` (matches lexical-scope rules).
        self.globals = Environment()

    # --------------------------------------------------------------- program

    def run_program(self, program: Program) -> str:
        try:
            for stmt in program.stmts:
                self.exec_stmt(stmt, self.globals)
        except _BreakSignal:
            raise Exception("'break' used outside of a loop")
        except _ContinueSignal:
            raise Exception("'continue' used outside of a loop")
        return "".join(self.output)

    # ------------------------------------------------------------ statements

    def exec_stmt(self, stmt: Any, env: Environment) -> None:
        if isinstance(stmt, ExprStmt):
            self.eval_expr(stmt.expr, env)
            return
        if isinstance(stmt, LetStmt):
            self.exec_let(stmt, env)
            return
        if isinstance(stmt, Block):
            self.exec_block(stmt, env.child())
            return
        if isinstance(stmt, IfStmt):
            self.exec_if(stmt, env)
            return
        if isinstance(stmt, WhileStmt):
            self.exec_while(stmt, env)
            return
        if isinstance(stmt, BreakStmt):
            # Caught by ``exec_while``; bubbling past it means we're not
            # inside a loop, which is a runtime error.
            raise _BreakSignal()
        if isinstance(stmt, ContinueStmt):
            raise _ContinueSignal()
        # Functions, return, for-in etc. land in later phases.
        raise Exception(
            f"unsupported statement {type(stmt).__name__} in phase 5"
        )

    def exec_let(self, stmt: LetStmt, env: Environment) -> None:
        value = self.eval_expr(stmt.value, env)
        if env.has_local(stmt.name):
            raise Exception(
                f"name '{stmt.name}' already declared in this scope"
            )
        env.define(stmt.name, value)

    def exec_block(self, block: Block, env: Environment) -> None:
        for inner in block.stmts:
            self.exec_stmt(inner, env)

    # ---------------------------------------------------------- control flow

    def exec_if(self, stmt: IfStmt, env: Environment) -> None:
        cond = self.eval_expr(stmt.cond, env)
        if is_truthy(cond):
            self._exec_branch(stmt.then_block, env)
        elif stmt.else_block is not None:
            # ``else_block`` may be either a ``Block`` (plain ``else { ... }``)
            # or another ``IfStmt`` (an ``else if`` chain). Both paths fall
            # through ``exec_stmt`` so block scoping stays consistent.
            self._exec_branch(stmt.else_block, env)

    def _exec_branch(self, node: Any, env: Environment) -> None:
        """Execute an if/else branch.

        A branch is normally a ``Block`` (open a fresh child scope) but in
        ``else if`` chains the parser stores a nested ``IfStmt`` directly,
        which we forward without a new scope (the inner ``if`` will create
        its own block scopes as needed).
        """
        if isinstance(node, Block):
            self.exec_block(node, env.child())
        else:
            self.exec_stmt(node, env)

    def exec_while(self, stmt: WhileStmt, env: Environment) -> None:
        while True:
            cond = self.eval_expr(stmt.cond, env)
            if not is_truthy(cond):
                return
            # Every iteration gets a fresh child scope so ``let`` inside
            # the body does not collide with itself across iterations.
            body = stmt.body
            try:
                if isinstance(body, Block):
                    self.exec_block(body, env.child())
                else:
                    # Defensive: parser should always emit a Block here, but
                    # if not, just exec it once in the current env.
                    self.exec_stmt(body, env)
            except _ContinueSignal:
                # Fall through to the next condition check.
                continue
            except _BreakSignal:
                return

    # ----------------------------------------------------------- expressions

    def eval_expr(self, expr: Any, env: Environment) -> Any:
        if isinstance(expr, NumberLit):
            return float(expr.value)
        if isinstance(expr, StringLit):
            return expr.value
        if isinstance(expr, BoolLit):
            return bool(expr.value)
        if isinstance(expr, NilLit):
            return None
        if isinstance(expr, Identifier):
            return self.lookup_name(expr.name, env)
        if isinstance(expr, Assign):
            return self.eval_assign(expr, env)
        if isinstance(expr, UnaryOp):
            return self.eval_unary(expr, env)
        if isinstance(expr, BinaryOp):
            return self.eval_binary(expr, env)
        if isinstance(expr, Call):
            return self.eval_call(expr, env)
        raise Exception(f"unsupported expression {type(expr).__name__}")

    # ---------------------------------------------------------- name lookup

    def lookup_name(self, name: str, env: Environment) -> Any:
        if env.has(name):
            return env.get(name)
        if name in self.builtins:
            return self.builtins[name]
        raise Exception(f"undefined name '{name}'")

    # ----------------------------------------------------------- assignment

    def eval_assign(self, node: Assign, env: Environment) -> Any:
        target = node.target
        # Phase 4 supports identifier targets only. Index targets land in
        # phases 8 / 9; the parser may already produce them, so we surface a
        # clear runtime error rather than silently miscompiling.
        if not isinstance(target, Identifier):
            raise Exception(
                f"cannot assign to {type(target).__name__} in phase 4"
            )
        value = self.eval_expr(node.value, env)
        if not env.assign(target.name, value):
            raise Exception(f"undefined name '{target.name}'")
        return value

    # -------------------------------------------------------------- unary op

    def eval_unary(self, node: UnaryOp, env: Environment) -> Any:
        if node.op == "-":
            value = self.eval_expr(node.operand, env)
            if not isinstance(value, float) or isinstance(value, bool):
                raise Exception(
                    f"unary '-' expects a number, got {_type_name(value)}"
                )
            return -value
        if node.op == "!":
            return not is_truthy(self.eval_expr(node.operand, env))
        raise Exception(f"unknown unary operator '{node.op}'")

    # ------------------------------------------------------------ binary op

    def eval_binary(self, node: BinaryOp, env: Environment) -> Any:
        op = node.op

        # Short-circuit logical operators — evaluate RHS only when needed,
        # and return the operand value (JS semantics), not a coerced bool.
        if op == "&&":
            left = self.eval_expr(node.left, env)
            if not is_truthy(left):
                return left
            return self.eval_expr(node.right, env)
        if op == "||":
            left = self.eval_expr(node.left, env)
            if is_truthy(left):
                return left
            return self.eval_expr(node.right, env)

        left = self.eval_expr(node.left, env)
        right = self.eval_expr(node.right, env)

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

    def eval_call(self, node: Call, env: Environment) -> Any:
        callee = self.eval_expr(node.callee, env)
        args = [self.eval_expr(a, env) for a in node.args]
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
