from tinylang.ast import *
from tinylang.environment import Environment
from tinylang.errors import TinyRuntimeError
from typing import Any, Dict, List

class Evaluator:
    def __init__(self, environment: Environment):
        self.environment = environment

    def evaluate(self, node: Any) -> Any:
        if isinstance(node, LetStmt):
            value = self.evaluate(node.value)
            self.environment.define(node.name, value)
            return value
        elif isinstance(node, IfStmt):
            condition = self.evaluate(node.condition)
            if condition:
                return self.evaluate(node.then_block)
            elif node.else_block is not None:
                return self.evaluate(node.else_block)
            return None
        elif isinstance(node, WhileStmt):
            while self.evaluate(node.condition):
                self.evaluate(node.block)
            return None
        elif isinstance(node, ForStmt):
            iterable = self.evaluate(node.iterable)
            if isinstance(iterable, List):
                for i, value in enumerate(iterable):
                    child_env = Environment(self.environment)
                    child_env.define(node.var1, value)
                    if node.var2 is not None:
                        child_env.define(node.var2, i)
                    self.evaluate(node.block, child_env)
            elif isinstance(iterable, Dict):
                for key, value in iterable.items():
                    child_env = Environment(self.environment)
                    child_env.define(node.var1, key)
                    child_env.define(node.var2, value)
                    self.evaluate(node.block, child_env)
            return None
        elif isinstance(node, FnDecl):
            # Implementation of function declaration
            pass
        elif isinstance(node, ReturnStmt):
            # Implementation of return statement
            pass
        elif isinstance(node, BreakStmt):
            # Implementation of break statement
            pass
        elif isinstance(node, ContinueStmt):
            # Implementation of continue statement
            pass
        elif isinstance(node, Block):
            for statement in node.statements:
                self.evaluate(statement)
            return None
        elif isinstance(node, ExprStmt):
            return self.evaluate(node.expression)
        elif isinstance(node, Assignment):
            value = self.evaluate(node.value)
            self.environment.assign(node.lvalue.value, value)
            return value
        elif isinstance(node, LogicOr):
            left = self.evaluate(node.left)
            if left:
                return left
            return self.evaluate(node.right)
        elif isinstance(node, LogicAnd):
            left = self.evaluate(node.left)
            if not left:
                return left
            return self.evaluate(node.right)
        elif isinstance(node, Equality):
            left = self.evaluate(node.left)
            right = self.evaluate(node.right)
            return left == right
        elif isinstance(node, Comparison):
            left = self.evaluate(node.left)
            right = self.evaluate(node.right)
            if node.operator == '<':
                return left < right
            elif node.operator == '>':
                return left > right
            elif node.operator == '<=':
                return left <= right
            elif node.operator == '>=':
                return left >= right
        elif isinstance(node, Term):
            left = self.evaluate(node.left)
            right = self.evaluate(node.right)
            if node.operator == '+':
                return left + right
            elif node.operator == '-':
                return left - right
        elif isinstance(node, Factor):
            left = self.evaluate(node.left)
            right = self.evaluate(node.right)
            if node.operator == '*':
                return left * right
            elif node.operator == '/':
                return left / right
            elif node.operator == '%':
                return left % right
        elif isinstance(node, Unary):
            operand = self.evaluate(node.operand)
            if node.operator == '!':
                return not operand
            elif node.operator == '-':
                return -operand
        elif isinstance(node, Call):
            # Implementation of function call
            pass
        elif isinstance(node, Primary):
            return node.value
        elif isinstance(node, ListLit):
            return [self.evaluate(element) for element in node.elements]
        elif isinstance(node, DictLit):
            return {self.evaluate(pair.key): self.evaluate(pair.value) for pair in node.pairs}
        elif isinstance(node, Pair):
            return Pair(self.evaluate(node.key), self.evaluate(node.value))
        elif isinstance(node, FnLit):
            # Implementation of function literal
            pass
        elif isinstance(node, LValue):
            return self.environment.get(node.value)
        elif isinstance(node, Args):
            return [self.evaluate(expression) for expression in node.expressions]
        else:
            raise TinyRuntimeError(f'Unknown node type: {type(node)}')

    def run(self, program: Program) -> None:
        for statement in program.statements:
            self.evaluate(statement)
