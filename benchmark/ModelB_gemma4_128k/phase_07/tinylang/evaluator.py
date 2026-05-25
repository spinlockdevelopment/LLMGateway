from typing import Any, List
from tinylang.lexer import tokenize
from tinylang.parser import Parser
from tinylang.ast import *
from tinylang.builtins import get_builtins

class Evaluator:
    def __init__(self):
        self.output_buffer: List[str] = []
        self.builtins = get_builtins(self.output_buffer)

    def is_truthy(self, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        return True

    def evaluate(self, node: Any) -> Any:
        if isinstance(node, Program):
            for stmt in node.stmts:
                self.evaluate(stmt)
            return None
        
        if isinstance(node, ExprStmt):
            return self.evaluate(node.expr)
        
        if isinstance(node, NumberLit):
            return node.value
        
        if isinstance(node, StringLit):
            return node.value
        
        if isinstance(node, BoolLit):
            return node.value
        
        if isinstance(node, NilLit):
            return None
        
        if isinstance(node, Identifier):
            if node.name in self.builtins:
                return self.builtins[node.name]
            raise Exception(f"Undefined identifier: {node.name}")
        
        if isinstance(node, BinaryOp):
            return self.evaluate_binary_op(node)
        
        if isinstance(node, UnaryOp):
            return self.evaluate_unary_op(node)
        
        if isinstance(node, Call):
            return self.evaluate_call(node)
        
        raise Exception(f"Unknown AST node: {type(node)}")

    def evaluate_binary_op(self, node: BinaryOp) -> Any:
        if node.op == "&&":
            left = self.evaluate(node.left)
            if not self.is_truthy(left):
                return left
            return self.evaluate(node.right)
        
        if node.op == "||":
            left = self.evaluate(node.left)
            if self.is_truthy(left):
                return left
            return self.evaluate(node.right)

        left = self.evaluate(node.left)
        right = self.evaluate(node.right)

        if node.op == "+":
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                return left + right
            if isinstance(left, str) and isinstance(right, str):
                return left + right
            raise Exception("Type error: + requires numbers or strings")
        
        if node.op in ("-", "*", "/", "%"):
            if not (isinstance(left, (int, float)) and isinstance(right, (int, float))):
                raise Exception(f"Type error: {node.op} requires numbers")
            if node.op == "-": return left - right
            if node.op == "*": return left * right
            if node.op == "/":
                if right == 0:
                    raise Exception("Division by zero")
                return left / right
            if node.op == "%": return left % right

        if node.op == "==":
            return left == right
        
        if node.op == "!=":
            return left != right

        if node.op in ("<", ">", "<=", ">="):
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                if node.op == "<": return left < right
                if node.op == ">": return left > right
                if node.op == "<=": return left <= right
                if node.op == ">=": return left >= right
            if isinstance(left, str) and isinstance(right, str):
                if node.op == "<": return left < right
                if node.op == ">": return left > right
                if node.op == "<=": return left <= right
                if node.op == ">=": return left >= right
            raise Exception(f"Type error: {node.op} requires same type (number or string)")

        raise Exception(f"Unknown binary operator: {node.op}")

    def evaluate_unary_op(self, node: UnaryOp) -> Any:
        if node.op == "!":
            return not self.is_truthy(self.evaluate(node.operand))
        if node.op == "-":
            val = self.evaluate(node.operand)
            if not isinstance(val, (int, float)):
                raise Exception("Type error: - requires number")
            return -val
        raise Exception(f"Unknown unary operator: {node.op}")

    def evaluate_call(self, node: Call) -> Any:
        callee = self.evaluate(node.callee)
        if not callable(callee):
            raise Exception("Can only call callables")
        args = [self.evaluate(arg) for arg in node.args]
        return callee(*args)

def run(source: str) -> str:
    tokens = tokenize(source)
    parser = Parser(tokens)
    program = parser.parse_program()
    evaluator = Evaluator()
    evaluator.evaluate(program)
    return "".join(evaluator.output_buffer)
