"""Built-in functions for tinylang."""

from typing import Any, List


def format_value(value: Any) -> str:
    """Format a tinylang value for printing."""
    if value is None:
        return "nil"
    elif isinstance(value, bool):
        return "true" if value else "false"
    elif isinstance(value, float):
        # If it's an integer value, print without decimal
        if value == int(value):
            return str(int(value))
        else:
            return str(value)
    elif isinstance(value, str):
        return value
    else:
        return str(value)


def builtin_print(*args) -> None:
    """Print function that returns formatted output."""
    formatted_args = [format_value(arg) for arg in args]
    return " ".join(formatted_args) + "\n"


# Registry of built-in functions
BUILTINS = {
    "print": builtin_print,
}