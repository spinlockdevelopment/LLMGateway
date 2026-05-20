from tinylang.lexer import tokenize
from tinylang.parser import parse
from tinylang.ast import *

def run(source):
    tokens = tokenize(source)
    ast = parse(tokens)
    evaluator = Evaluator()
    evaluator.evaluate(ast)
    return evaluator.output

class Evaluator:
    def __init__(self):
        self.output = ''
        self.stack = []

    def evaluate(self, node):
        if isinstance(node, Program):
            for statement in node.statements:
                self.evaluate(statement)
        elif isinstance(node, ExpressionStatement):
            self.evaluate(node.expression)
        elif isinstance(node, BinaryExpression):
            left = self.evaluate(node.left)
            right = self.evaluate(node.right)
            if node.operator == '+':
                if isinstance(left, str) and isinstance(right, str):
                    return left + right
                elif isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return float(left) + float(right)
                else:
                    raise Exception('Type error: + operator requires two numbers or two strings')
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
                    raise Exception('Type error: < operator requires two numbers or two strings')
            elif node.operator == '>':
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left > right
                elif isinstance(left, str) and isinstance(right, str):
                    return left > right
                else:
                    raise Exception('Type error: > operator requires two numbers or two strings')
            elif node.operator == '<=':
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left <= right
                elif isinstance(left, str) and isinstance(right, str):
                    return left <= right
                else:
                    raise Exception('Type error: <= operator requires two numbers or two strings')
            elif node.operator == '>=':
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left >= right
                elif isinstance(left, str) and isinstance(right, str):
                    return left >= right
                else:
                    raise Exception('Type error: >= operator requires two numbers or two strings')
            elif node.operator == '&&':
                return left if not left else right
            elif node.operator == '||':
                return left if left else right
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
        elif isinstance(node, PrintStatement):
            args = [self.evaluate(arg) for arg in node.args]
            formatted_args = []
            for arg in args:
                if isinstance(arg, bool):
                    formatted_args.append('true' if arg else 'false')
                elif isinstance(arg, float):
                    formatted_args.append(repr(arg).rstrip('.0') if arg.is_integer() else repr(arg))
                elif arg is None:
                    formatted_args.append('nil')
                else:
                    formatted_args.append(str(arg))
            self.output += ' '.join(formatted_args) + '\n'
        else:
            raise Exception(f'Unknown node type: {type(node)}')
