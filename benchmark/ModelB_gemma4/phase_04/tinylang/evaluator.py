import io
from tinylang.lexer import tokenize
from tinylang.parser import Parser
from tinylang.ast import (
    Program, Statement, Expr, ExprStmt, NumberLit, StringLit,
    BoolLit, NilLit, BinaryOp, UnaryOp, Call, Identifier,
    LetStmt, Block, Assign, IfStmt, WhileStmt, ForStmt,
    FnDecl, ReturnStmt, BreakStmt, ContinueStmt
)
from tinylang.builtins import format_tinylang_value
from tinylang.environment import Environment


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
            # Phase 5
            pass
        elif isinstance(stmt, WhileStmt):
            # Phase 5
            pass
        elif isinstance(stmt, ForStmt):
            # Phase 5
            pass
        elif isinstance(stmt, FnDecl):
            # Phase 6
            pass
        elif isinstance(stmt, ReturnStmt):
            # Phase 6
            pass
        elif isinstance(stmt, BreakStmt):
            # Phase 5
            pass
        elif isinstance(stmt, ContinueStmt):
            # Phase 5
            pass
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
        if isinstance(expr, BinaryOp):
            return self.evaluate_binary_op(expr)
        if isinstance(expr, UnaryOp):
            return self.evaluate_unary_op(expr)
        if isinstance(expr, Call):
            return self.evaluate_call(expr)
        if isinstance(expr, Identifier):
            return self.environment.get(expr.name)
        if isinstance(expr, Assign):
            if isinstance(expr.target, Identifier):
                value = self.evaluate_expr(expr.value)
                self.environment.assign(expr.target.name, value)
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
        raise Exception(f"Unknown function call: {expr.callee}")

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
