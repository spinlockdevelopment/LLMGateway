from tinylang.ast import Node, Program, FnDecl, FnLit, Call, ReturnStmt, ListLit, Index, Assign
from tinylang.builtins import BUILTINS

class Evaluator:
    def __init__(self):
        self.env = {}

    def evaluate(self, node):
        if isinstance(node, ListLit):
            return [self.evaluate(element) for element in node.elements]
        elif isinstance(node, Index):
            target = self.evaluate(node.target)
            index = self.evaluate(node.index)
            if not isinstance(index, float) or index != int(index):
                raise RuntimeError(f"Index must be an integer, got {index}")
            index = int(index)
            if not isinstance(target, list):
                raise RuntimeError(f"Cannot index into non-list value {target}")
            if index < 0 or index >= len(target):
                raise RuntimeError(f"Index {index} out of range for list of length {len(target)}")
            return target[index]
        elif isinstance(node, Assign) and isinstance(node.target, Index):
            target = self.evaluate(node.target.target)
            index = self.evaluate(node.target.index)
            value = self.evaluate(node.value)
            if not isinstance(index, float) or index != int(index):
                raise RuntimeError(f"Index must be an integer, got {index}")
            index = int(index)
            if not isinstance(target, list):
                raise RuntimeError(f"Cannot index into non-list value {target}")
            if index < 0 or index >= len(target):
                raise RuntimeError(f"Index {index} out of range for list of length {len(target)}")
            target[index] = value
            return value
        elif isinstance(node, Assign):
            target = node.target
            value = self.evaluate(node.value)
            self.env[target] = value
            return value
        elif isinstance(node, Program):
            for statement in node.statements:
                self.evaluate(statement)
            return None
        elif isinstance(node, FnDecl):
            self.env[node.name] = Function(node.params, node.body, self.env)
            return None
        elif isinstance(node, FnLit):
            return Function(node.params, node.body, self.env)
        elif isinstance(node, Call):
            func = self.evaluate(node.func)
            args = [self.evaluate(arg) for arg in node.args]
            if not isinstance(func, Function):
                raise RuntimeError(f"Attempt to call non-function {func}")
            if len(args) != len(func.params):
                raise RuntimeError(f"Expected {len(func.params)} arguments, got {len(args)}")
            new_env = func.env.copy()
            new_env.update(zip(func.params, args))
            evaluator = Evaluator()
            evaluator.env = new_env
            for statement in func.body.statements:
                result = evaluator.evaluate(statement)
                if isinstance(statement, ReturnStmt):
                    return result
            return None
        elif isinstance(node, ReturnStmt):
            return self.evaluate(node.value)
        elif isinstance(node, Node):
            raise RuntimeError(f"Unsupported node type: {type(node)}")
        else:
            return node


class Function:
    def __init__(self, params, body, env):
        self.params = params
        self.body = body
        self.env = env

    def __repr__(self):
        return f"Function({self.params}, {self.body}, {self.env})"


def run(node, env=None):
    evaluator = Evaluator()
    if env is not None:
        evaluator.env = env
    return evaluator.evaluate(node)
