from tinylang.ast import *
from tinylang.environment import Environment
from tinylang.errors import TinylangError, ParseError, RuntimeError as TinyRuntimeError
from typing import Any, Dict, List, Optional

class Function:
    def __init__(self, params: List[str], body: Block, env: Environment):
        self.params = params
        self.body = body
        self.env = env

    def call(self, args: List[Any]) -> Any:
        if len(args) != len(self.params):
            raise TinyRuntimeError(f'Expected {len(self.params)} arguments, got {len(args)}')
        call_env = Environment(self.env)
        for param, arg in zip(self.params, args):
            call_env.values[param] = arg
        return Evaluator(call_env).evaluate_block(self.body)



def eval_fn_decl(node, env):
    pass
def eval_fn_lit(node, env):
    pass
def eval_call(node, env):
    pass
def eval_return_stmt(node, env):
    pass
class ReturnStmt:
    pass
    def evaluate(self, node: Expression) -> Any:
        if isinstance(node, Assignment):
            value = self.evaluate(node.value)
            self.env.values[node.lvalue.name] = value
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
            if node.operator == '==':
                return left == right
            elif node.operator == '!=':
                return left != right
            else:
                raise TinylangError(f'Unknown operator {node.operator}')
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
            else:
                raise TinylangError(f'Unknown operator {node.operator}')
        elif isinstance(node, Term):
            left = self.evaluate(node.left)
            right = self.evaluate(node.right)
            if node.operator == '+':
                return left + right
            elif node.operator == '-':
                return left - right
            else:
                raise TinylangError(f'Unknown operator {node.operator}')
        elif isinstance(node, Factor):
            left = self.evaluate(node.left)
            right = self.evaluate(node.right)
            if node.operator == '*':
                return left * right
            elif node.operator == '/':
                return left / right
            elif node.operator == '%':
                return left % right
            else:
                raise TinylangError(f'Unknown operator {node.operator}')
        elif isinstance(node, Unary):
            operand = self.evaluate(node.operand)
            if node.operator == '!':
                return not operand
            elif node.operator == '-':
                return -operand
            else:
                raise TinylangError(f'Unknown operator {node.operator}')
        elif isinstance(node, Call):
            func = self.evaluate(node.function)
            args = [self.evaluate(arg) for arg in node.args]
            if isinstance(func, Function):
                return func.call(args)
            else:
                raise TinyRuntimeError(f'Attempt to call non-function {func}')
        elif isinstance(node, Primary):
            return node.value
        elif isinstance(node, ListLit):
            return [self.evaluate(elem) for elem in node.elements]
        elif isinstance(node, DictLit):
            return {self.evaluate(pair.key): self.evaluate(pair.value) for pair in node.pairs}
        elif isinstance(node, FnLit):
            return Function(node.params, node.body, self.env)
        else:
            raise TinylangError(f'Unknown expression type {type(node)}')

    def evaluate_block(self, block: Block) -> Any:
        result = None
        for statement in block.statements:
            if isinstance(statement, LetStmt):
                self.env.values[statement.name] = self.evaluate(statement.value)
            elif isinstance(statement, IfStmt):
                condition = self.evaluate(statement.condition)
                if condition:
                    result = self.evaluate_block(statement.then_block)
                elif statement.else_block:
                    result = self.evaluate_block(statement.else_block)
            elif isinstance(statement, WhileStmt):
                while self.evaluate(statement.condition):
                    result = self.evaluate_block(statement.block)
            elif isinstance(statement, ForStmt):
                iterable = self.evaluate(statement.iterable)
                if isinstance(iterable, list):
                    for i, v in enumerate(iterable):
                        self.env.values[statement.var_name] = v
                        if statement.index_name:
                            self.env.values[statement.index_name] = i
                        result = self.evaluate_block(statement.block)
                else:
                    raise TinyRuntimeError(f'Cannot iterate over non-list {iterable}')
            elif isinstance(statement, FnDecl):
                self.env.values[statement.name] = Function(statement.params, statement.body, self.env)
            elif isinstance(statement, ReturnStmt):
                if statement.value:
                    return self.evaluate(statement.value)
                return None
            elif isinstance(statement, BreakStmt):
                raise TinylangError('Break statement outside loop')
            elif isinstance(statement, ContinueStmt):
                raise TinylangError('Continue statement outside loop')
            elif isinstance(statement, Block):
                result = self.evaluate_block(statement)
            elif isinstance(statement, ExprStmt):
                result = self.evaluate(statement.expression)
            else:
                raise TinylangError(f'Unknown statement type {type(statement)}')
        return result

    def evaluate_program(self, program: Program) -> Any:
        return self.evaluate_block(program)
