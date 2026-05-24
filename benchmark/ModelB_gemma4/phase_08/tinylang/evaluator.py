import io
from dataclasses import dataclass
from tinylang.lexer import tokenize
from tinylang.parser import Parser
from tinylang.ast import (

    Program, Statement, Expr, ExprStmt, NumberLit, StringLit,
    BoolLit, NilLit, BinaryOp, UnaryOp, Call, Identifier,
    LetStmt, Block, Assign, IfStmt, WhileStmt, ForStmt,
    FnDecl, ReturnStmt, FnLit, BreakStmt, ContinueStmt,
    ListLit, Index
)
from tinylang.builtins import (
    format_tinylang_value,
    len_builtin,
    push_builtin,
    pop_builtin,
)

from tinylang.environment import Environment
from tinylang.errors import RuntimeError as TinyRuntimeError


class _BreakSignal(Exception):
    pass


class _ContinueSignal(Exception):
    pass


class _ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value


@dataclass
class Function:
    params: list[str]
    body: Block
    env: Environment


class Evaluator:
    def __init__(self):
        self.output = io.StringIO()
        self.environment = Environment()

    def run(self, source: str) -> str:
        tokens = tokenize(source)
        parser = Parser(tokens)
        program = parser.parse()
        self.evaluate_program(program)
        return self.output.getvalue()

    def evaluate_program(self, program: Program):
        for stmt in program.stmts:
            self.evaluate_statement(stmt)

    def evaluate_statement(self, stmt: Statement):
        if isinstance(stmt, ExprStmt):
            self.evaluate_expr(stmt.expr)
        elif isinstance(stmt, LetStmt):
            value = self.evaluate_expr(stmt.value)
            self.environment.define(stmt.name, value)
        elif isinstance(stmt, Block):
            old_env = self.environment
            self.environment = Environment(parent=old_env)
            for s in stmt.stmts:
                self.evaluate_statement(s)
            self.environment = old_env
        elif isinstance(stmt, IfStmt):
            condition = self.evaluate_expr(stmt.cond)
            if self.is_truthy(condition):
                self.evaluate_statement(stmt.then_block)
            elif stmt.else_block is not None:
                self.evaluate_statement(stmt.else_block)
        elif isinstance(stmt, WhileStmt):
            while self.is_truthy(self.evaluate_expr(stmt.cond)):
                try:
                    self.evaluate_statement(stmt.body)
                except _ContinueSignal:
                    continue
                except _BreakSignal:
                    break
        elif isinstance(stmt, ForStmt):
            # Phase 9
            pass
        elif isinstance(stmt, FnDecl):
            func = Function(params=stmt.params, body=stmt.body, env=self.environment)
            self.environment.define(stmt.name, func)
        elif isinstance(stmt, ReturnStmt):
            raise _ReturnSignal(self.evaluate_expr(stmt.value))
        elif isinstance(stmt, BreakStmt):
            raise _BreakSignal()
        elif isinstance(stmt, ContinueStmt):
            raise _ContinueSignal()
        else:
            raise Exception(f"Unknown statement type: {type(stmt)}")

    def evaluate_expr(self, expr: Expr) -> any:
        if isinstance(expr, NumberLit):
            return expr.value
        if isinstance(expr, StringLit):
            return expr.value
        if isinstance(expr, BoolLit):
            return expr.value
        if isinstance(expr, NilLit):
            return None
        if isinstance(expr, ListLit):
            return [self.evaluate_expr(item) for item in expr.items]
        if isinstance(expr, Index):
            target = self.evaluate_expr(expr.target)
            if not isinstance(target, list):
                raise TinyRuntimeError(f"Cannot index non-list value: {type(target)}")
            key = self.evaluate_expr(expr.key)
            if not isinstance(key, float) or not key.is_integer():
                raise TinyRuntimeError(f"Index must be an integer")
            idx = int(key)
            if idx < 0 or idx >= len(target):
                raise TinyRuntimeError(f"Index out of range")
            return target[idx]
        if isinstance(expr, BinaryOp):
            return self.evaluate_binary_op(expr)
        if isinstance(expr, UnaryOp):
            return self.evaluate_unary_op(expr)
        if isinstance(expr, Call):
            return self.evaluate_call(expr)
        if isinstance(expr, Identifier):
            return self.environment.get(expr.name)
        if isinstance(expr, FnLit):
            return Function(params=expr.params, body=expr.body, env=self.environment)
        if isinstance(expr, Assign):
            if isinstance(expr.target, Identifier):
                value = self.evaluate_expr(expr.value)
                self.environment.assign(expr.target.name, value)
                return value
            if isinstance(expr.target, Index):
                target = self.evaluate_expr(expr.target.target)
                if not isinstance(target, list):
                    raise TinyRuntimeError(f"Cannot index non-list value: {type(target)}")
                key = self.evaluate_expr(expr.target.key)
                if not isinstance(key, float) or not key.is_integer():
                    raise TinyRuntimeError(f"Index must be an integer")
                idx = int(key)
                if idx < 0 or idx >= len(target):
                    raise TinyRuntimeError(f"Index out of range")
                value = self.evaluate_expr(expr.value)
                target[idx] = value
                return value
            raise Exception(f"Assignment to {type(expr.target)} is not supported yet")
        raise Exception(f"Unknown expression type: {type(expr)}")

    def evaluate_binary_op(self, expr: BinaryOp) -> any:
        if expr.op == "&&":
            left = self.evaluate_expr(expr.left)
            if self.is_truthy(left):
                return self.evaluate_expr(expr.right)
            return left
        if expr.op == "||":
            left = self.evaluate_expr(expr.left)
            if self.is_truthy(left):
                return left
            return self.evaluate_expr(expr.right)

        left = self.evaluate_expr(expr.left)
        right = self.evaluate_expr(expr.right)

        if expr.op == "+":
            if isinstance(left, str) and isinstance(right, str):
                return left + right
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                return float(left + right)
            raise Exception("Type error: cannot add string and number")
        
        if expr.op == "-":
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                return float(left - right)
            raise Exception("Type error: cannot subtract non-numbers")

        if expr.op == "*":
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                return float(left * right)
            raise Exception("Type error: cannot multiply non-numbers")

        if expr.op == "/":
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                if right == 0:
                    raise Exception("Division by zero")
                return float(left / right)
            raise Exception("Type error: cannot divide non-numbers")

        if expr.op == "%":
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                return float(left % right)
            raise Exception("Type error: cannot modulo non-numbers")

        if expr.op == "==":
            return left == right
        
        if expr.op == "!=":
            return left != right

        if expr.op == "<":
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                return left < right
            if isinstance(left, str) and isinstance(right, str):
                return left < right
            raise Exception("Type error: cannot compare different types")

        if expr.op == ">":
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                return left > right
            if isinstance(left, str) and isinstance(right, str):
                return left > right
            raise Exception("Type error: cannot compare different types")

        if expr.op == "<=":
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                return left <= right
            if isinstance(left, str) and isinstance(right, str):
                return left <= right
            raise Exception("Type error: cannot compare different types")

        if expr.op == ">=":
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                return left >= right
            if isinstance(left, str) and isinstance(right, str):
                return left >= right
            raise Exception("Type error: cannot compare different types")

        raise Exception(f"Unknown binary operator: {expr.op}")

    def evaluate_unary_op(self, expr: UnaryOp) -> any:
        operand = self.evaluate_expr(expr.operand)
        if expr.op == "!":
            return not self.is_truthy(operand)
        if expr.op == "-":
            if isinstance(operand, (int, float)):
                return float(-operand)
            raise Exception("Type error: cannot negate non-number")
        raise Exception(f"Unknown unary operator: {expr.op}")

    def evaluate_call(self, expr: Call) -> any:
        # For now, only print is supported.
        if isinstance(expr.callee, Identifier) and expr.callee.name == "print":
            args = [self.evaluate_expr(arg) for arg in expr.args]
            self.output.write(" ".join(format_tinylang_value(arg) for arg in args) + "\n")
            return None
        
        callee_val = self.evaluate_expr(expr.callee)
        if not isinstance(callee_val, Function):
            raise Exception(f"Cannot call non-function value: {callee_val}")
        
        args = [self.evaluate_expr(arg) for arg in expr.args]
        if len(args) != len(callee_val.params):
            raise Exception(f"Arity mismatch: expected {len(callee_val.params)}, got {len(args)}")
        
        # Create a fresh child env whose parent is the function's defining environment
        new_env = Environment(parent=callee_val.env)
        for param, arg_val in zip(callee_val.params, args):
            new_env.define(param, arg_val)
        
        old_env = self.environment
        self.environment = new_env
        try:
            for s in callee_val.body.stmts:
                self.evaluate_statement(s)
            return None
        except _ReturnSignal as e:
            return e.value
        finally:
            self.environment = old_env

    def is_truthy(self, v) -> bool:
        if v is None:
            return False
        if isinstance(v, bool):
            return v
        if isinstance(v, float):
            return v != 0.0
        return True

def run(source: str) -> str:
    evaluator = Evaluator()
    return evaluator.run(source)
