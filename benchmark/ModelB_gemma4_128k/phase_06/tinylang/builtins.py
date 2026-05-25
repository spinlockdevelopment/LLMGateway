from typing import Any, Callable, Dict, List

def get_builtins(output_buffer: List[str]) -> Dict[str, Callable]:
    def print_(*args: Any) -> None:
        formatted_args = []
        for arg in args:
            if arg is None:
                formatted_args.append("nil")
            elif isinstance(arg, bool):
                formatted_args.append("true" if arg else "false")
            elif isinstance(arg, (int, float)):
                s = repr(arg)
                if s.endswith(".0"):
                    formatted_args.append(s[:-2])
                else:
                    formatted_args.append(s)
            elif isinstance(arg, str):
                formatted_args.append(arg)
            else:
                formatted_args.append(str(arg))
        output_buffer.append(" ".join(formatted_args) + "\n")

    return {
        "print": print_,
    }
