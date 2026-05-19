from tinylang.ast import FnDecl, FnLit, Call, ReturnStmt
from tinylang.evaluator import Function, run
from tinylang.environment import Environment


def evaluate(node, env):
    if isinstance(node, FnDecl):
        func = Function(node.params, node.body, env)
        env[node.name] = func
        return None
    elif isinstance(node, FnLit):
        return Function(node.params, node.body, env)
    elif isinstance(node, Call):
        func = evaluate(node.callee, env)
        if not isinstance(func, Function):
            raise RuntimeError(f"Cannot call non-function value")
        args = [evaluate(arg, env) for arg in node.args]
        if len(args) != len(func.params):
            raise RuntimeError(f"Arity mismatch: expected {len(func.params)}, got {len(args)}")
        child_env = Environment(func.env)
        for param, arg in zip(func.params, args):
            child_env[param] = arg
        return run(func.body, child_env)
    elif isinstance(node, ReturnStmt):
        return node.value
    else:
        raise NotImplementedError(f"Node type {type(node)} not implemented")
