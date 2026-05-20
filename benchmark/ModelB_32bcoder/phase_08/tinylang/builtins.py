def len_(x):
    if isinstance(x, list):
        return float(len(x))
    elif isinstance(x, str):
        return float(len(x))
    else:
        raise RuntimeError(f"len() expects a list or string, got {x}")

def push(xs, v):
    if not isinstance(xs, list):
        raise RuntimeError(f"push() expects a list, got {xs}")
    xs.append(v)
    return None

def pop(xs):
    if not isinstance(xs, list):
        raise RuntimeError(f"pop() expects a list, got {xs}")
    if len(xs) == 0:
        raise RuntimeError("pop() from empty list")
    return xs.pop()

BUILTINS = {
    'len': len_,
    'push': push,
    'pop': pop,
}

def print_(*args):
    print(*args)

BUILTINS['print'] = print_
