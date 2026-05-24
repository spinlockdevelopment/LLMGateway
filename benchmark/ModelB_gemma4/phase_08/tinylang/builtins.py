def format_tinylang_value(v) -> str:
    if v is None:
        return "nil"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        if v.is_integer():
            return str(int(v))
        return str(v)
    if isinstance(v, list):
        return "[" + ", ".join(format_tinylang_value(x) for x in v) + "]"
    return str(v)

def len_builtin(x):
    if isinstance(x, list):
        return len(x)
    if isinstance(x, str):
        return len(x)
    raise Exception("len() argument must be a list or string")

def push_builtin(xs, v):
    if not isinstance(xs, list):
        raise Exception("push() argument must be a list")
    xs.append(v)
    return None

def pop_builtin(xs):
    if not isinstance(xs, list):
        raise Exception("pop() argument must be a list")
    if not xs:
        raise Exception("pop from empty list")
    return xs.pop()
