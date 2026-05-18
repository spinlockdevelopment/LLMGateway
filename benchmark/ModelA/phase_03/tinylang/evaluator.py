"""Evaluator for tinylang expressions and statements."""

from typing import Any
from .lexer import tokenize
from .parser import Parser
from .ast import *
from .builtins import BUILTINS


class Evaluator:
    def __init__(self):
        self.output_buffer = []
    
    def evaluate_program(self, program: Program) -> str:
        """Evaluate a program and return captured output."""
        self.output_buffer = []
        
        for stmt in program.stmts:
            self.evaluate_stmt(stmt)
        
        return "".join(self.output_buffer)
    
    def evaluate_stmt(self, stmt: Stmt) -> Any:
        """Evaluate a statement."""
        if isinstance(stmt, ExprStmt):
            return self.evaluate_expr(stmt.expr)
        else:
            raise Exception(f"Unsupported statement type: {type(stmt)}")
    
    def evaluate_expr(self, expr: Expr) -> Any:
        """Evaluate an expression and return its value."""
        if isinstance(expr, NumberLit):
            return expr.value
        
        elif isinstance(expr, StringLit):
            return expr.value
        
        elif isinstance(expr, BoolLit):
            return expr.value
        
        elif isinstance(expr, NilLit):
            return None
        
        elif isinstance(expr, BinaryOp):
            return self.evaluate_binary_op(expr)
        
        elif isinstance(expr, UnaryOp):
            return self.evaluate_unary_op(expr)
        
        elif isinstance(expr, Call):
            return self.evaluate_call(expr)
        
        elif isinstance(expr, Identifier):
            # For now, only built-in functions are supported
            if expr.name in BUILTINS:
                return BUILTINS[expr.name]
            else:
                raise Exception(f"Undefined variable: {expr.name}")
        
        else:
            raise Exception(f"Unsupported expression type: {type(expr)}")
    
    def evaluate_binary_op(self, expr: BinaryOp) -> Any:
        """Evaluate a binary operation."""
        left = self.evaluate_expr(expr.left)
        
        # Short-circuit evaluation for logical operators
        if expr.op == "&&":
            if not self.is_truthy(left):
                return left
            return self.evaluate_expr(expr.right)
        
        elif expr.op == "||":
            if self.is_truthy(left):
                return left
            return self.evaluate_expr(expr.right)
        
        # For other operators, evaluate both sides
        right = self.evaluate_expr(expr.right)
        
        if expr.op == "+":
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                return left + right
            elif isinstance(left, str) and isinstance(right, str):
                return left + right
            else:
                raise Exception(f"Cannot add {type(left).__name__} and {type(right).__name__}")
        
        elif expr.op == "-":
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                return left - right
            else:
                raise Exception(f"Cannot subtract {type(right).__name__} from {type(left).__name__}")
        
        elif expr.op == "*":
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                return left * right
            else:
                raise Exception(f"Cannot multiply {type(left).__name__} and {type(right).__name__}")
        
        elif expr.op == "/":
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                if right == 0:
                    raise Exception("Division by zero")
                return left / right
            else:
                raise Exception(f"Cannot divide {type(left).__name__} by {type(right).__name__}")
        
        elif expr.op == "%":
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                if right == 0:
                    raise Exception("Division by zero")
                return left % right
            else:
                raise Exception(f"Cannot take modulo of {type(left).__name__} and {type(right).__name__}")
        
        elif expr.op == "==":
            return left == right
        
        elif expr.op == "!=":
            return left != right
        
        elif expr.op in ["<", ">", "<=", ">="]:
            return self.evaluate_comparison(expr.op, left, right)
        
        else:
            raise Exception(f"Unsupported binary operator: {expr.op}")
    
    def evaluate_comparison(self, op: str, left: Any, right: Any) -> bool:
        """Evaluate comparison operators."""
        # Check that both operands are the same type and comparable
        if type(left) != type(right):
            raise Exception(f"Cannot compare {type(left).__name__} and {type(right).__name__}")
        
        if not isinstance(left, (int, float, str)):
            raise Exception(f"Cannot compare values of type {type(left).__name__}")
        
        if op == "<":
            return left < right
        elif op == ">":
            return left > right
        elif op == "<=":
            return left <= right
        elif op == ">=":
            return left >= right
        else:
            raise Exception(f"Unknown comparison operator: {op}")
    
    def evaluate_unary_op(self, expr: UnaryOp) -> Any:
        """Evaluate a unary operation."""
        operand = self.evaluate_expr(expr.operand)
        
        if expr.op == "!":
            return not self.is_truthy(operand)
        
        elif expr.op == "-":
            if isinstance(operand, (int, float)):
                return -operand
            else:
                raise Exception(f"Cannot negate {type(operand).__name__}")
        
        else:
            raise Exception(f"Unsupported unary operator: {expr.op}")
    
    def evaluate_call(self, expr: Call) -> Any:
        """Evaluate a function call."""
        callee = self.evaluate_expr(expr.callee)
        args = [self.evaluate_expr(arg) for arg in expr.args]
        
        if callable(callee):
            result = callee(*args)
            # If it's the print function, capture its output
            if callee == BUILTINS.get("print"):
                self.output_buffer.append(result)
                return None  # print returns nil
            return result
        else:
            raise Exception(f"Cannot call {type(callee).__name__}")
    
    def is_truthy(self, value: Any) -> bool:
        """Determine if a value is truthy in tinylang."""
        if value is None or value is False or value == 0:
            return False
        return True


def run(source: str) -> str:
    """Parse and execute tinylang source code, returning captured output."""
    tokens = tokenize(source)
    parser = Parser(tokens)
    program = parser.parse()
    
    evaluator = Evaluator()
    return evaluator.evaluate_program(program)