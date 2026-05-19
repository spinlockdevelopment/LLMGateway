from tinylang.ast import LetStmt, Block, Identifier, Assign
from tinylang.environment import Environment
from tinylang.errors import TinyRuntimeError


def run(source):
    # Placeholder for actual parsing logic
    # For now, we assume the source is already parsed into an AST
    ast = parse(source)
    env = Environment()
    return evaluate(ast, env)


def evaluate(node, env):
    if isinstance(node, LetStmt):
        env.define(node.name, evaluate(node.value, env))
        return None
    elif isinstance(node, Block):
        result = None
        for stmt in node.statements:
            result = evaluate(stmt, Environment(parent=env))
        return result
    elif isinstance(node, Identifier):
        return lookup_variable(node.name, env)
    elif isinstance(node, Assign):
        if isinstance(node.target, Identifier):
            value = evaluate(node.value, env)
            assign_variable(node.target.name, value, env)
            return value
        else:
            raise TinyRuntimeError(f'Invalid assignment target: {node.target}')
    else:
        raise TinyRuntimeError(f'Unknown node type: {type(node)}')


def lookup_variable(name, env):
    current = env
    while current is not None:
        if name in current.locals:
            return current.locals[name]
        current = current.parent
    raise TinyRuntimeError(f'Undefined variable: {name}')


def assign_variable(name, value, env):
    current = env
    while current is not None:
        if name in current.locals:
            current.locals[name] = value
            return
        current = current.parent
    raise TinyRuntimeError(f'Undefined variable: {name}')