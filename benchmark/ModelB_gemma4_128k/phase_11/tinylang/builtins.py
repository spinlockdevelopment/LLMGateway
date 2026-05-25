from typing import Any, Callable, Dict, List
from tinylang.errors import TinyRuntimeError

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
            elif isinstance(arg, dict):
                # {"a": 1, "b": 2} style
                parts = []
                for k, v in arg.items():
                    k_str = f'"{k}"' if isinstance(k, str) else str(k)
                    v_str = str(v) # This is a placeholder
                    parts.append(f"{k_str}: {v_str}")
                formatted_args.append("{" + ", ".join(parts) + "}")
            else:
                formatted_args.append(str(arg))
        output_buffer.append(" ".join(formatted_args) + "\n")

    def keys(d: dict) -> List[Any]:
        if not isinstance(d, dict):
            raise TinyRuntimeError("keys() requires a dict")
        return list(d.keys())

    def values(d: dict) -> List[Any]:
        if not isinstance(d, dict):
            raise TinyRuntimeError("values() requires a dict")
        return list(d.values())

    def has(d: dict, k: Any) -> bool:
        if not isinstance(d, dict):
            raise TinyRuntimeError("has() requires a dict")
        return k in d

    def del_key(d: dict, k: Any) -> None:
        if not isinstance(d, dict):
            raise TinyRuntimeError("del() requires a dict")
        if k not in d:
            raise TinyRuntimeError(f"Key {k} not found in dict")
        del d[k]

    return {
        "print": print_,
        "keys": keys,
        "values": values,
        "has": has,
        "del": del_key,
    }
