from tinylang.errors import TinyRuntimeError


def len_(x):
    if isinstance(x, list):
        return len(x)
    else:
        raise TinyRuntimeError(f"len() expects a list, got {type(x).__name__}")

def push(xs, v):
    if isinstance(xs, list):
        xs.append(v)
        return None
    else:
        raise TinyRuntimeError(f"push() expects a list, got {type(xs).__name__}")

def pop(xs):
    if isinstance(xs, list) and xs:
        return xs.pop()
    else:
        raise TinyRuntimeError(f"pop() expects a non-empty list, got {type(xs).__name__}")
