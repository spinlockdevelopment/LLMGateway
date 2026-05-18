from tinylang.parser import parse
from tinylang.ast import *
from tinylang.builtins import print_builtin
from tinylang.lexer import tokenize
from typing import Any, Dict, List
import sys

class RuntimeError(Exception):
    def __init__(self, message: str, line: int = 0, col: int = 0):
        self.message = message
        self.line = line
        self.col = col
        super().__init__(f"Runtime error at line {line}, column {col}: {message}")

class Evaluator:
    def __init__(self):
        self.builtins = {
            'print': print_builtin
        }
    
    def evaluate(self, node: Any, env: Dict[str, Any] = None) -> Any:
        if env is None:
            env = {}
        
        if isinstance(node, Program):
            return self._evaluate_program(node, env)
        elif isinstance(node, ExprStmt):
            return self._evaluate_expr_stmt(node, env)
        elif isinstance(node, BinaryOp):
            return self._evaluate_binary_op(node, env)
        elif isinstance(node, UnaryOp):
            return self._evaluate_unary_op(node, env)
        elif isinstance(node, Call):
            return self._evaluate_call(node, env)
        elif isinstance(node, NumberLit):
            return self._evaluate_number_lit(node, env)
        elif isinstance(node, StringLit):
            return self._evaluate_string_lit(node, env)
        elif isinstance(node, BoolLit):
            return self._evaluate_bool_lit(node, env)
        elif isinstance(node, NilLit):
            return self._evaluate_nil_lit(node, env)
        elif isinstance(node, Identifier):
            return self._evaluate_identifier(node, env)
        elif isinstance(node, Assign):
            return self._evaluate_assign(node, env)
        elif isinstance(node, Block):
            return self._evaluate_block(node, env)
        else:
            raise RuntimeError(f"Unknown node type: {type(node)}")

    def _evaluate_program(self, program: Program, env: Dict[str, Any]) -> str:
        output = ""
        for stmt in program.stmts:
            result = self.evaluate(stmt, env)
            if result is not None and not isinstance(result, (int, float, bool, type(None))):
                output += str(result)
        return output

    def _evaluate_expr_stmt(self, stmt: ExprStmt, env: Dict[str, Any]) -> Any:
        return self.evaluate(stmt.expr, env)

    def _evaluate_binary_op(self, op: BinaryOp, env: Dict[str, Any]) -> Any:
        left = self.evaluate(op.left, env)
        right = self.evaluate(op.right, env)
        
        # Handle arithmetic operations
        if op.op in ['+', '-', '*', '/', '%']:
            return self._evaluate_arithmetic_op(op.op, left, right)
        elif op.op in ['==', '!=']:
            return self._evaluate_equality_op(op.op, left, right)
        elif op.op in ['<', '>', '<=', '>=']:
            return self._evaluate_comparison_op(op.op, left, right)
        elif op.op == '&&':
            return self._evaluate_logical_and(left, right, env)
        elif op.op == '||':
            return self._evaluate_logical_or(left, right, env)
        else:
            raise RuntimeError(f"Unknown binary operator: {op.op}")

    def _evaluate_arithmetic_op(self, op: str, left: Any, right: Any) -> Any:
        # Handle string concatenation
        if op == '+' and isinstance(left, str) and isinstance(right, str):
            return left + right
        # Handle numeric operations
        if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
            if op == '+':
                raise RuntimeError("Cannot add non-numeric types", 0, 0)
            raise RuntimeError("Cannot perform arithmetic on non-numeric types", 0, 0)
        
        if op == '+':
            return left + right
        elif op == '-':
            return left - right
        elif op == '*':
            return left * right
        elif op == '/':
            if right == 0:
                raise RuntimeError("Division by zero", 0, 0)
            return left / right
        elif op == '%':
            if right == 0:
                raise RuntimeError("Modulo by zero", 0, 0)
            return left % right

    def _evaluate_equality_op(self, op: str, left: Any, right: Any) -> bool:
        if op == '==':
            return left == right
        elif op == '!=':
            return left != right

    def _evaluate_comparison_op(self, op: str, left: Any, right: Any) -> bool:
        # Check if both operands are compatible for comparison
        if isinstance(left, str) and isinstance(right, str):
            pass  # Both strings, OK
        elif isinstance(left, (int, float)) and isinstance(right, (int, float)):
            pass  # Both numbers, OK
        else:
            # Mixed types - not allowed for comparison
            raise RuntimeError("Cannot compare different types", 0, 0)
        
        if op == '<':
            return left < right
        elif op == '>':
            return left > right
        elif op == '<=':
            return left <= right
        elif op == '>=':
            return left >= right

    def _evaluate_logical_and(self, left: Any, right: Any, env: Dict[str, Any]) -> Any:
        left_value = self.evaluate(left, env)
        if not self._is_truthy(left_value):
            return left_value
        return self.evaluate(right, env)

    def _evaluate_logical_or(self, left: Any, right: Any, env: Dict[str, Any]) -> Any:
        left_value = self.evaluate(left, env)
        if self._is_truthy(left_value):
            return left_value
        return self.evaluate(right, env)

    def _is_truthy(self, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        return True

    def _evaluate_unary_op(self, op: UnaryOp, env: Dict[str, Any]) -> Any:
        operand = self.evaluate(op.operand, env)
        if op.op == '!':
            return not self._is_truthy(operand)
        elif op.op == '-':
            if not isinstance(operand, (int, float)):
                raise RuntimeError("Cannot negate non-numeric type", 0, 0)
            return -operand
        else:
            raise RuntimeError(f"Unknown unary operator: {op.op}")

    def _evaluate_number_lit(self, lit: NumberLit, env: Dict[str, Any]) -> float:
        return lit.value

    def _evaluate_string_lit(self, lit: StringLit, env: Dict[str, Any]) -> str:
        return lit.value

    def _evaluate_bool_lit(self, lit: BoolLit, env: Dict[str, Any]) -> bool:
        return lit.value

    def _evaluate_nil_lit(self, lit: NilLit, env: Dict[str, Any]) -> None:
        return None

    def _evaluate_identifier(self, ident: Identifier, env: Dict[str, Any]) -> Any:
        if ident.name in env:
            return env[ident.name]
        elif ident.name in self.builtins:
            return self.builtins[ident.name]
        else:
            raise RuntimeError(f"Undefined variable: {ident.name}", 0, 0)

    def _evaluate_assign(self, assign: Assign, env: Dict[str, Any]) -> Any:
        value = self.evaluate(assign.value, env)
        if isinstance(assign.target, Identifier):
            env[assign.target.name] = value
            return value
        else:
            raise RuntimeError("Cannot assign to non-identifier", 0, 0)

    def _evaluate_call(self, call: Call, env: Dict[str, Any]) -> Any:
        callee = self.evaluate(call.callee, env)
        args = [self.evaluate(arg, env) for arg in call.args]
        
        if callable(callee):
            return callee(*args)
        else:
            raise RuntimeError("Cannot call non-callable", 0, 0)

    def _evaluate_block(self, block: Block, env: Dict[str, Any]) -> Any:
        result = None
        for stmt in block.stmts:
            result = self.evaluate(stmt, env)
        return result

def run(source: str) -> str:
    """Execute a tinylang program and return the output from print statements."""
    try:
        tokens = tokenize(source)
        program = parse(tokens)
        evaluator = Evaluator()
        return evaluator.evaluate(program)
    except Exception as e:
        # Re-raise with more context if needed
        raise e