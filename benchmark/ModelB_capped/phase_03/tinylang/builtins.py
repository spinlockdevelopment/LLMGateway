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
        else:
            str_args.append(str(arg))
    
    # Join with spaces and add newline
    output = " ".join(str_args) + "\n"
    return output