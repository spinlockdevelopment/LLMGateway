from tinylang.ast import *
from tinylang.errors import TinyRuntimeError
from typing import Any, Dict, List

class Builtins:
    @staticmethod
def keys(d: Dict) -> List:
    return list(d.keys())

    @staticmethod
def values(d: Dict) -> List:
    return list(d.values())

    @staticmethod
def has(d: Dict, k: Any) -> bool:
    return k in d

    @staticmethod
def del_(d: Dict, k: Any) -> None:
    if k in d:
        del d[k]
    else:
        raise TinyRuntimeError(f'Missing key: {k}')

    @staticmethod
def print(*args: Any) -> None:
    print(*args)

    @staticmethod
def len_(x: Any) -> int:
    if isinstance(x, (str, list, dict)):
        return len(x)
    else:
        raise TinyRuntimeError(f'Unsupported type for len(): {type(x)}')

    @staticmethod
def push(xs: List, v: Any) -> None:
    xs.append(v)

    @staticmethod
def pop(xs: List) -> Any:
    if xs:
        return xs.pop()
    else:
        raise TinyRuntimeError('pop from empty list')

    @staticmethod
def range_(n: int) -> List[int]:
    return list(range(n))

    @staticmethod
def range2(a: int, b: int) -> List[int]:
    return list(range(a, b))

    @staticmethod
def str_(x: Any) -> str:
    return str(x)

    @staticmethod
def num(x: Any) -> float:
    if isinstance(x, (int, float)):
        return float(x)
    elif isinstance(x, str):
        try:
            return float(x)
        except ValueError:
            raise TinyRuntimeError(f'Invalid number format: {x}')
    else:
        raise TinyRuntimeError(f'Unsupported type for num(): {type(x)}')
