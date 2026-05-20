from tinylang.ast import *
from tinylang.environment import Environment
from tinylang.errors import TinylangError, RuntimeError as TinyRuntimeError
from typing import Any, List, Optional

class BreakSignal(Exception):
    pass
class ContinueSignal(Exception):
    pass

def evaluate_expression(expr: Expression, env: Environment) -> Any:
    if isinstance(expr, Primary):
        return expr.value
    elif isinstance(expr, Unary):
        operand = evaluate_expression(expr.operand, env)
        if expr.operator == '-':
            return -operand
        elif expr.operator == '!':
            return not operand
    elif isinstance(expr, Call):
        callee = evaluate_expression(expr.callee, env)
        args = [evaluate_expression(arg, env) for arg in expr.args]
        if not callable(callee):
            raise TinyRuntimeError(f'Attempt to call non-callable {callee}')
        return callee(*args)
    elif isinstance(expr, Assignment):
        lvalue = expr.lvalue
        value = evaluate_expression(expr.value, env)
        if isinstance(lvalue, LValue):
            env.set(lvalue.name, value)
        return value
    elif isinstance(expr, LogicOr):
        left = evaluate_expression(expr.left, env)
        if left:
            return left
        return evaluate_expression(expr.right, env)
    elif isinstance(expr, LogicAnd):
        left = evaluate_expression(expr.left, env)
        if not left:
            return left
        return evaluate_expression(expr.right, env)
    elif isinstance(expr, Equality):
        left = evaluate_expression(expr.left, env)
        right = evaluate_expression(expr.right, env)
        if expr.operator == '==':
            return left == right
        elif expr.operator == '!=':
            return left != right
    elif isinstance(expr, Comparison):
        left = evaluate_expression(expr.left, env)
        right = evaluate_expression(expr.right, env)
        if expr.operator == '<':
            return left < right
        elif expr.operator == '>':
            return left > right
        elif expr.operator == '<=':
            return left <= right
        elif expr.operator == '>=':
            return left >= right
    elif isinstance(expr, Term):
        left = evaluate_expression(expr.left, env)
        right = evaluate_expression(expr.right, env)
        if expr.operator == '+':
            return left + right
        elif expr.operator == '-':
            return left - right
    elif isinstance(expr, Factor):
        left = evaluate_expression(expr.left, env)
        right = evaluate_expression(expr.right, env)
        if expr.operator == '*':
            return left * right
        elif expr.operator == '/':
            return left / right
        elif expr.operator == '%':
            return left % right
    else:
        raise TinylangError(f'Unknown expression type: {expr}')

def evaluate_statement(stmt: Statement, env: Environment) -> None:
    if isinstance(stmt, LetStmt):
        value = evaluate_expression(stmt.value, env)
        env.set(stmt.name, value)
    elif isinstance(stmt, IfStmt):
        condition = evaluate_expression(stmt.condition, env)
        if condition:
            evaluate_block(stmt.then_branch, env)
        elif stmt.else_branch:
            evaluate_block(stmt.else_branch, env)
    elif isinstance(stmt, WhileStmt):
        while True:
            condition = evaluate_expression(stmt.condition, env)
            if not condition:
                break
            try:
                evaluate_block(stmt.body, Environment(parent=env))
            except BreakSignal:
                break
            except ContinueSignal:
                continue
    elif isinstance(stmt, BreakStmt):
        raise BreakSignal()
    elif isinstance(stmt, ContinueStmt):
        raise ContinueSignal()
    elif isinstance(stmt, Block):
        evaluate_block(stmt, env)
    elif isinstance(stmt, ExprStmt):
        evaluate_expression(stmt.expression, env)
    elif isinstance(stmt, ReturnStmt):
        value = evaluate_expression(stmt.value, env) if stmt.value else None
        raise TinylangError(f'Return statement not implemented yet: {value}')
    elif isinstance(stmt, FnDecl):
        fn_env = Environment(parent=env)
        fn_env.set(stmt.name, Function(stmt.params, stmt.body, fn_env))
    else:
        raise TinylangError(f'Unknown statement type: {stmt}')

def evaluate_block(block: Block, env: Environment) -> None:
    for stmt in block.statements:
        evaluate_statement(stmt, env)

class Function:
    def __init__(self, params: List[str], body: Block, env: Environment):
        self.params = params
        self.body = body
        self.env = env

    def __call__(self, *args: Any) -> Any:
        if len(args) != len(self.params):
            raise TinyRuntimeError(f'Expected {len(self.params)} arguments but got {len(args)}')
        call_env = Environment(parent=self.env)
        for param, arg in zip(self.params, args):
            call_env.set(param, arg)
        try:
            evaluate_block(self.body, call_env)
        except TinylangError as e:
            raise TinyRuntimeError(f'Function call error: {e}')

    def __repr__(self) -> str:
        return f'<Function params={self.params}>'

def run(source: str) -> str:
    from tinylang.parser import parse
    from tinylang.lexer import tokenize
    tokens = tokenize(source)
    program = parse(tokens)
    env = Environment()
    try:
        evaluate_block(program, env)
    except TinyRuntimeError as e:
        print(f'Runtime error: {e}')
    return ''
