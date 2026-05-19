from tinylang.ast import *
from tinylang.errors import TinyRuntimeError


class Evaluator:
    def __init__(self):
        self.output = []

    def run(self, program):
        for stmt in program:
            self.evaluate(stmt)
        return ''.join(self.output)

    def evaluate(self, node):
        if isinstance(node, Number):
            return node.value
        elif isinstance(node, String):
            return node.value
        elif isinstance(node, Boolean):
            return node.value
        elif isinstance(node, BinaryOp):
            left = self.evaluate(node.left)
            right = self.evaluate(node.right)
            if node.op == '+':
                if isinstance(left, str) and isinstance(right, str):
                    return left + right
                elif isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left + right
                else:
                    raise TinyRuntimeError("Type error in addition")
            elif node.op == '-':
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left - right
                else:
                    raise TinyRuntimeError("Type error in subtraction")
            elif node.op == '*':
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left * right
                else:
                    raise TinyRuntimeError("Type error in multiplication")
            elif node.op == '/':
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    if right == 0:
                        raise TinyRuntimeError("Division by zero")
                    return left / right
                else:
                    raise TinyRuntimeError("Type error in division")
            elif node.op == '%':
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    if right == 0:
                        raise TinyRuntimeError("Division by zero")
                    return left % right
                else:
                    raise TinyRuntimeError("Type error in modulo")
            elif node.op == '==':
                return left == right
            elif node.op == '!=':
                return left != right
            elif node.op == '<':
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left < right
                elif isinstance(left, str) and isinstance(right, str):
                    return left < right
                else:
                    raise TinyRuntimeError("Type error in comparison")
            elif node.op == '>':
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left > right
                elif isinstance(left, str) and isinstance(right, str):
                    return left > right
                else:
                    raise TinyRuntimeError("Type error in comparison")
            elif node.op == '<=':
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left <= right
                elif isinstance(left, str) and isinstance(right, str):
                    return left <= right
                else:
                    raise TinyRuntimeError("Type error in comparison")
            elif node.op == '>=':
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left >= right
                elif isinstance(left, str) and isinstance(right, str):
                    return left >= right
                else:
                    raise TinyRuntimeError("Type error in comparison")
            elif node.op == '&&':
                if self.is_truthy(left):
                    return self.evaluate(right)
                else:
                    return left
            elif node.op == '||':
                if self.is_truthy(left):
                    return left
                else:
                    return self.evaluate(right)
            elif node.op == '!':
                return not self.is_truthy(node.right)
        elif isinstance(node, Print):
            values = [str(self.evaluate(arg)) for arg in node.args]
            self.output.append(' '.join(values) + '\n')
        else:
            raise TinyRuntimeError(f'Unsupported node type: {type(node)}')

    def is_truthy(self, value):
        return value is not None and value is not False and value != 0
