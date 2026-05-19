from tinylang.ast import ListLit, Index, Assign
from tinylang.errors import TinyRuntimeError
from tinylang.environment import Environment


def evaluate_list_lit(node, env):
    return [evaluate(element, env) for element in node.elements]

def evaluate_index(node, env):
    target = evaluate(node.target, env)
    index = evaluate(node.index, env)
    if not isinstance(index, float) or index % 1 != 0:
        raise TinyRuntimeError(f"Index {index} is not an integer")
    index = int(index)
    if index < 0 or index >= len(target):
        raise TinyRuntimeError(f"Index {index} out of range")
    return target[index]

def evaluate_assign(node, env):
    if isinstance(node.target, Index):
        target = evaluate(node.target.target, env)
        index = evaluate(node.target.index, env)
        if not isinstance(index, float) or index % 1 != 0:
            raise TinyRuntimeError(f"Index {index} is not an integer")
        index = int(index)
        if index < 0 or index >= len(target):
            raise TinyRuntimeError(f"Index {index} out of range")
        target[index] = evaluate(node.value, env)
        return target[index]
    else:
        raise TinyRuntimeError("Unsupported assignment target")
