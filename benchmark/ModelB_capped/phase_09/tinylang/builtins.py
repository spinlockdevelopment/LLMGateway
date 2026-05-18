def print_func(*args):
    """Print function implementation."""
    # Convert arguments to strings
    str_args = []
    for arg in args:
        if arg is None:
            str_args.append("nil")
        elif isinstance(arg, bool):
            str_args.append(str(arg).lower())
        elif isinstance(arg, float):
            if arg.is_integer():
                str_args.append(str(int(arg)))
            else:
                str_args.append(str(arg))
        elif isinstance(arg, list):
            # Handle list printing
            elements = []
            for item in arg:
                if item is None:
                    elements.append("nil")
                elif isinstance(item, bool):
                    elements.append(str(item).lower())
                elif isinstance(item, float):
                    if item.is_integer():
                        elements.append(str(int(item)))
                    else:
                        elements.append(str(item))
                else:
                    elements.append(str(item))
            str_args.append("[" + ", ".join(elements) + "]")
        elif isinstance(arg, dict):
            # Handle dict printing
            pairs = []
            for k, v in arg.items():
                if isinstance(k, str):
                    key_str = f'"{k}"'
                else:
                    key_str = str(k)
                if v is None:
                    value_str = "nil"
                elif isinstance(v, bool):
                    value_str = str(v).lower()
                elif isinstance(v, float):
                    if v.is_integer():
                        value_str = str(int(v))
                    else:
                        value_str = str(v)
                else:
                    value_str = str(v)
                pairs.append(f"{key_str}: {value_str}")
            str_args.append("{" + ", ".join(pairs) + "}")
        else:
            str_args.append(str(arg))
    
    # Join with spaces and add newline
    output = " ".join(str_args) + "\n"
    return output

def len_func(x):
    """Return length of a list or string."""
    if isinstance(x, list):
        return len(x)
    elif isinstance(x, str):
        return len(x)
    elif isinstance(x, dict):
        return len(x)
    else:
        raise RuntimeError("len() can only be called on lists, strings, or dicts")

def push(xs, v):
    """Append v to list xs, mutates in place, returns nil."""
    if not isinstance(xs, list):
        raise RuntimeError("push() can only be called on lists")
    xs.append(v)
    return None

def pop(xs):
    """Remove and return last element from list."""
    if not isinstance(xs, list):
        raise RuntimeError("pop() can only be called on lists")
    if len(xs) == 0:
        raise RuntimeError("pop() on empty list")
    return xs.pop()

def keys(d):
    """Return list of keys in dict."""
    if not isinstance(d, dict):
        raise RuntimeError("keys() can only be called on dicts")
    return list(d.keys())

def values(d):
    """Return list of values in dict."""
    if not isinstance(d, dict):
        raise RuntimeError("values() can only be called on dicts")
    return list(d.values())

def has(d, k):
    """Return bool indicating if dict has key."""
    if not isinstance(d, dict):
        raise RuntimeError("has() can only be called on dicts")
    return k in d

def del_func(d, k):
    """Remove key from dict, returns nil."""
    if not isinstance(d, dict):
        raise RuntimeError("del() can only be called on dicts")
    if k not in d:
        raise RuntimeError("del() key not found in dict")
    del d[k]
    return None