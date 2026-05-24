def format_tinylang_value(v) -> str:
    if v is None:
        return "nil"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        if v.is_integer():
            return str(int(v))
        return str(v)
    if isinstance(v, str):
        return f'"{v}"'
    if isinstance(v, list):
        return "[" + ", ".join(format_tinylang_value(x) for x in v) + "]"
    if isinstance(v, dict):
        items = []
        for k, val in v.items():
            k_str = format_tinylang_value(k)
            v_str = format_tinylang_value(val)
            items.append(f"{k_str}: {v_str}")
        return "{" + ", ".join(items) + "}"
    return str(v)

def len_builtin(x):
    if isinstance(x, list):
        return len(x)
    if isinstance(x, str):
        return len(x)
    if isinstance(x, dict):
        return len(x)
    raise Exception("len() argument must be a list, string, or dict")

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

def keys_builtin(d):
    if not isinstance(d, dict):
        raise Exception("keys() argument must be a dict")
    return list(d.keys())

def values_builtin(d):
    if not isinstance(d, dict):
        raise Exception("values() argument must be a dict")
    return list(d.values())

def has_builtin(d, k):
    if not isinstance(d, dict):
        raise Exception("has() first argument must be a dict")
    return k in d

def del_builtin(d, k):
    if not isinstance(d, dict):
        raise Exception("del() first argument must be a dict")
    if k not in d:
        raise Exception(f"Key '{k}' not found in dict")
    del d[k]
    return None
