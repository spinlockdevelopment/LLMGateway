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
    else:
        raise RuntimeError("len() can only be called on lists or strings")

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