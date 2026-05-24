import io
from tinylang.lexer import tokenize
from tinylang.parser import Parser
from tinylang.ast import (
    Program, Statement, Expr, ExprStmt, NumberLit, StringLit,
    BoolLit, NilLit, BinaryOp, UnaryOp, Call, Identifier
)
from tinylang.builtins import format_tinylang_value

class Evaluator:
    def __init__(self):
        self.output = io.StringIO()

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
        # Other statements are out of scope for now.

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
            # This should probably be handled by environment, but for now
            # we don't have variables. However, print is a call to an identifier.
            # If it's just an identifier, it's an error or we return it.
            # But in this phase, identifiers are only used in calls or as part of other exprs.
            # Actually, an expression can be just an identifier.
            # But we don't have an environment yet.
            raise Exception(f"Identifier {expr.name} is not defined")
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
