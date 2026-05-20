from tinylang.ast import LetStmt, Block, Identifier, Assign, Program, ExpressionStmt, Number, PrintStmt
from tinylang.environment import Environment
from tinylang.errors import RuntimeError

def evaluate(node, env):
    if isinstance(node, Program):
        for statement in node.statements:
            evaluate(statement, env)
    elif isinstance(node, LetStmt):
        value = evaluate(node.value, env)
        env.define(node.name, value)
    elif isinstance(node, Block):
        block_env = Environment(env)
        for statement in node.statements:
            evaluate(statement, block_env)
    elif isinstance(node, Assign):
        value = evaluate(node.value, env)
        env.assign(node.target.name, value)
    elif isinstance(node, Identifier):
        return env.lookup(node.name)
    elif isinstance(node, ExpressionStmt):
        evaluate(node.expression, env)
    elif isinstance(node, PrintStmt):
        print_values = [evaluate(arg, env) for arg in node.args]
        print(*print_values)
    elif isinstance(node, Number):
        return node.value
    else:
        raise RuntimeError(f"Unknown node type: {type(node)}")

def run(source):
    from tinylang.parser import parse
    ast = parse(source)
    env = Environment()
    evaluate(ast, env)
    return ''