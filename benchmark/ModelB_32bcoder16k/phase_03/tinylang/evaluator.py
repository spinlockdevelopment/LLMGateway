from tinylang.lexer import tokenize
from tinylang.parser import parse
from tinylang.ast import Program, ExpressionStatement, BinaryExpression, UnaryExpression, Literal, CallExpression, Identifier

class Evaluator:
    def __init__(self):
        self.output = []
        self.builtins = {
            'print': self.builtin_print
        }

    def run(self, source):
        tokens = tokenize(source)
        ast = parse(tokens)
        self.evaluate(ast)
        return ''.join(self.output)

    def evaluate(self, node):
        if isinstance(node, Program):
            for statement in node.statements:
                self.evaluate(statement)
        elif isinstance(node, ExpressionStatement):
            self.evaluate(statement.expression)
        elif isinstance(node, BinaryExpression):
            left = self.evaluate(node.left)
            right = self.evaluate(node.right)
            if node.operator == '+':
                if isinstance(left, str) and isinstance(right, str):
                    return left + right
                elif isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return float(left) + float(right)
                else:
                    raise Exception('Type error: cannot add non-number and non-string types')
            elif node.operator == '-':
                return float(left) - float(right)
            elif node.operator == '*':
                return float(left) * float(right)
            elif node.operator == '/':
                if right == 0:
                    raise Exception('Division by zero')
                return float(left) / float(right)
            elif node.operator == '%':
                return float(left) % float(right)
            elif node.operator == '==':
                return left == right
            elif node.operator == '!=':
                return left != right
            elif node.operator == '<':
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left < right
                elif isinstance(left, str) and isinstance(right, str):
                    return left < right
                else:
                    raise Exception('Type error: cannot compare different types')
            elif node.operator == '>':
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left > right
                elif isinstance(left, str) and isinstance(right, str):
                    return left > right
                else:
                    raise Exception('Type error: cannot compare different types')
            elif node.operator == '<=':
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left <= right
                elif isinstance(left, str) and isinstance(right, str):
                    return left <= right
                else:
                    raise Exception('Type error: cannot compare different types')
            elif node.operator == '>=':
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left >= right
                elif isinstance(left, str) and isinstance(right, str):
                    return left >= right
                else:
                    raise Exception('Type error: cannot compare different types')
            elif node.operator == '&&':
                if not left:
                    return left
                return right
            elif node.operator == '||':
                if left:
                    return left
                return right
            else:
                raise Exception(f'Unknown operator: {node.operator}')
        elif isinstance(node, UnaryExpression):
            operand = self.evaluate(node.operand)
            if node.operator == '!':
                return not operand
            elif node.operator == '-':
                return -float(operand)
            else:
                raise Exception(f'Unknown operator: {node.operator}')
        elif isinstance(node, Literal):
            return node.value
        elif isinstance(node, CallExpression):
            if isinstance(node.callee, Identifier):
                func_name = node.callee.name
                if func_name in self.builtins:
                    args = [self.evaluate(arg) for arg in node.arguments]
                    return self.builtins[func_name](*args)
                else:
                    raise Exception(f'Unknown function: {func_name}')
            else:
                raise Exception('Function calls must be to identifiers')
        elif isinstance(node, Identifier):
            raise Exception('Identifier evaluation not implemented yet')
        else:
            raise Exception(f'Unknown node type: {type(node)}')

    def builtin_print(self, *args):
        formatted_args = []
        for arg in args:
            if isinstance(arg, float) and arg.is_integer():
                formatted_args.append(str(int(arg)))
            else:
                formatted_args.append(repr(arg).strip('"'))
        self.output.append(' '.join(formatted_args) + '\n')


def run(source):
    evaluator = Evaluator()
    return evaluator.run(source)
