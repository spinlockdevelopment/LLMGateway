def print_builtin(*args):
    """Built-in print function that formats arguments and returns the result"""
    formatted_args = []
    for arg in args:
        if isinstance(arg, bool):
            formatted_args.append("true" if arg else "false")
        elif arg is None:
            formatted_args.append("nil")
        elif isinstance(arg, str):
            formatted_args.append(arg)
        elif isinstance(arg, (int, float)):
            if isinstance(arg, int) or (isinstance(arg, float) and arg.is_integer()):
                formatted_args.append(str(int(arg)))
            else:
                formatted_args.append(repr(arg).rstrip('0').rstrip('.'))
        else:
            formatted_args.append(str(arg))
    
    result = " ".join(formatted_args) + "\n"
    return result