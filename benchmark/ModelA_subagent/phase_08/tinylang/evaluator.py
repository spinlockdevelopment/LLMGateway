"""Tree-walking evaluator for tinylang — phases 1-7.

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

Phase 6 adds first-class functions:

* ``fn name(params) { ... }`` declarations and ``fn(params) { ... }``
  function-literal expressions. A declaration is sugar for a ``let`` that
  binds the function in the current scope; the binding happens *before* the
  body runs so the function can recurse via its own name.
* A :class:`Function` value type that captures the parameter list, body
  ``Block``, and the **defining** environment (the environment active at
  the point the ``fn`` was evaluated). Calls execute the body in a fresh
  child of that defining env (not the caller's env), which sets up the
  lexical-closure semantics phase 7 will exercise.
* ``return`` statements, implemented as a private signal exception caught
  by the nearest enclosing call. ``return;`` (no value) yields ``nil``.
* Arity and callability errors surfaced as plain :class:`Exception` for
  now; phase 10 will wrap these into the public error hierarchy.

Phase 7 — closures. No new AST and no new public surface; the work here
is a correctness pass on phase 6's environment model. The invariants the
evaluator now relies on (and that the closure tests probe) are:

1.  **Lexical capture by reference.** A function literal stores its
    *defining* :class:`Environment` (``fn.env``) at the moment ``FnLit``
    or ``FnDecl`` is evaluated. It does not re-resolve names against the
    caller's environment, and it does not snapshot the captured values
    into a new dict — it keeps the live ``Environment`` instance.
2.  **Calls extend the captured env.** ``_invoke_function`` allocates the
    parameter scope as ``fn.env.child()``, never as ``caller_env.child()``.
    This is what makes scoping lexical rather than dynamic.
3.  **Shared mutation between sibling closures.** Two function literals
    evaluated under the same parent ``Environment`` capture *the same*
    parent object, so any ``assign`` that walks up into that parent (via
    :meth:`Environment.assign`, which mutates the chain in place) is
    visible to every closure capturing it. The counter / pair patterns
    in the spec rely on this.
4.  **Captured envs outlive the call that created them.** Python keeps
    the parent ``Environment`` alive through the ``Function.env``
    reference even after the outer call has returned; the call-time
    child scope is dropped, but the captured parent (with its ``let n``)
    is not.

These properties already follow from the phase 4 ``Environment`` design
and the phase 6 ``Function`` shape; phase 7 ratifies them and the test
suite exercises them.

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
    FnDecl,
    FnLit,
    Identifier,
    IfStmt,
    Index,
    LetStmt,
    ListLit,
    NilLit,
    NumberLit,
    Program,
    ReturnStmt,
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


class _ReturnSignal(Exception):
    """Raised by ``return``; caught only by the nearest enclosing call."""

    __slots__ = ("value",)

    def __init__(self, value: Any) -> None:
        super().__init__()
        self.value = value


# --------------------------------------------------------------------------- #
# Function value                                                              #
# --------------------------------------------------------------------------- #


class Function:
    """A user-defined tinylang function — also the closure value type.

    Holds the parameter name list, the body ``Block`` AST, the **defining
    environment** (a live :class:`Environment` instance, not a snapshot of
    its values), and an optional ``name`` used purely for nicer error
    messages / ``repr``.

    Storing the live ``Environment`` is what makes this object a closure:
    when the function is invoked, the call-time scope is built as a child
    of ``self.env`` (see ``_Evaluator._invoke_function``), so free-variable
    lookups walk up into the original defining chain. Mutations via
    ``Environment.assign`` rebind in place, so two ``Function`` values
    capturing the same parent observe each other's writes — the property
    the phase 7 spec's counter / adder / pair examples depend on.
    """

    __slots__ = ("params", "body", "env", "name")

    def __init__(
        self,
        params: list,
        body: Any,
        env: "Environment",
        name: str = "<anonymous>",
    ) -> None:
        self.params = list(params)
        self.body = body
        self.env = env
        self.name = name

    @property
    def arity(self) -> int:
        return len(self.params)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<fn {self.name}({', '.join(self.params)})>"


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
        except _ReturnSignal:
            raise Exception("'return' used outside of a function")
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
        if isinstance(stmt, FnDecl):
            self.exec_fn_decl(stmt, env)
            return
        if isinstance(stmt, ReturnStmt):
            # ``return;`` (no value) yields ``nil`` per the spec.
            value = None
            if stmt.value is not None:
                value = self.eval_expr(stmt.value, env)
            raise _ReturnSignal(value)
        # for-in etc. land in later phases.
        raise Exception(
            f"unsupported statement {type(stmt).__name__} in phase 6"
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

    # ------------------------------------------------------------- functions

    def exec_fn_decl(self, stmt: FnDecl, env: Environment) -> None:
        """``fn name(params) { ... }`` — desugar into a ``let``.

        The :class:`Function` value is built with ``env`` as its defining
        scope, then bound under ``stmt.name`` in that same scope. We bind
        *before* the body ever runs so that recursive references resolve
        to this function via the normal lookup chain.
        """
        if env.has_local(stmt.name):
            raise Exception(
                f"name '{stmt.name}' already declared in this scope"
            )
        fn = Function(
            params=stmt.params,
            body=stmt.body,
            env=env,
            name=stmt.name,
        )
        env.define(stmt.name, fn)

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
        if isinstance(expr, FnLit):
            # Capture ``env`` *by reference* — this is the closure step.
            # The Function value keeps the live Environment so later calls
            # see (and can mutate) bindings declared in the scope where the
            # ``fn`` literal was evaluated.
            return Function(
                params=expr.params,
                body=expr.body,
                env=env,
                name="<anonymous>",
            )
        if isinstance(expr, ListLit):
            # Items evaluate left-to-right in the current env.
            return [self.eval_expr(item, env) for item in expr.items]
        if isinstance(expr, Index):
            return self.eval_index(expr, env)
        raise Exception(f"unsupported expression {type(expr).__name__}")

    # --------------------------------------------------------------- indexing

    def eval_index(self, node: Index, env: Environment) -> Any:
        """``target[key]`` — phase 8 handles list targets only."""
        target = self.eval_expr(node.target, env)
        key = self.eval_expr(node.key, env)
        if isinstance(target, list):
            idx = self._coerce_list_index(key)
            if idx < 0 or idx >= len(target):
                raise Exception(
                    f"list index out of range: {idx} (len={len(target)})"
                )
            return target[idx]
        if isinstance(target, str):
            # Strings aren't required to be indexable in phase 8, but the
            # spec leaves it open. Reject explicitly with a clear message.
            raise Exception("indexing strings is not supported")
        raise Exception(
            f"cannot index {_type_name(target)} (only lists are indexable)"
        )

    @staticmethod
    def _coerce_list_index(key: Any) -> int:
        """Convert a tinylang index value to a Python ``int``.

        The spec says list indices must be numbers with no fractional part;
        ``true``/``false`` and other types are rejected. Negative indices
        also fall through to the caller, which raises out-of-range.
        """
        if isinstance(key, bool) or not isinstance(key, float):
            raise Exception(
                f"list index must be a number, got {_type_name(key)}"
            )
        if not key.is_integer():
            raise Exception(f"list index must be a whole number, got {key!r}")
        return int(key)

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
        if isinstance(target, Identifier):
            value = self.eval_expr(node.value, env)
            if not env.assign(target.name, value):
                raise Exception(f"undefined name '{target.name}'")
            return value
        if isinstance(target, Index):
            return self._assign_index(target, node.value, env)
        raise Exception(
            f"cannot assign to {type(target).__name__}"
        )

    def _assign_index(self, target: Index, value_expr: Any, env: Environment) -> Any:
        """``xs[i] = v`` — phase 8 supports list targets only.

        The container, the key, then the RHS are evaluated in that order
        (matches the source order). Out-of-range indices on assignment are
        a runtime error — no auto-growth, per the brief.
        """
        container = self.eval_expr(target.target, env)
        key = self.eval_expr(target.key, env)
        value = self.eval_expr(value_expr, env)
        if isinstance(container, list):
            idx = self._coerce_list_index(key)
            if idx < 0 or idx >= len(container):
                raise Exception(
                    f"list index out of range: {idx} (len={len(container)})"
                )
            container[idx] = value
            return value
        raise Exception(
            f"cannot index-assign into {_type_name(container)} "
            f"(only lists are supported)"
        )

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
        # Args evaluate left-to-right in the *caller's* env, per the spec.
        args = [self.eval_expr(a, env) for a in node.args]
        if isinstance(callee, Function):
            return self._invoke_function(callee, args)
        if callable(callee):
            # Built-ins (Python callables) — arity is enforced by the
            # built-in itself; we just forward.
            return callee(*args)
        raise Exception(f"cannot call {_type_name(callee)}")

    def _invoke_function(self, fn: "Function", args: list) -> Any:
        if len(args) != fn.arity:
            raise Exception(
                f"function '{fn.name}' expects {fn.arity} argument"
                f"{'' if fn.arity == 1 else 's'}, got {len(args)}"
            )
        # Fresh child of the *defining* environment — this is what makes
        # closures lexical. The caller's env is irrelevant to body lookups;
        # free variables resolve up through ``fn.env``, and writes to those
        # variables (via ``Environment.assign``) land in the captured scope,
        # which is how shared mutable state between sibling closures works.
        call_env = fn.env.child()
        for param, value in zip(fn.params, args):
            call_env.define(param, value)
        try:
            self.exec_block(fn.body, call_env)
        except _ReturnSignal as r:
            return r.value
        # Falling off the end of a function yields ``nil``.
        return None


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
    if isinstance(value, Function):
        return "function"
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
