from tinylang.ast import DictLit, DictGet, DictSet, ForStmt
from tinylang.errors import TinyRuntimeError

def keys(d):
    if not isinstance(d, dict):
        raise TinyRuntimeError(f'Expected dict, got {type(d).__name__}')
    return list(d.keys())

def values(d):
    if not isinstance(d, dict):
        raise TinyRuntimeError(f'Expected dict, got {type(d).__name__}')
    return list(d.values())

def has(d, k):
    if not isinstance(d, dict):
        raise TinyRuntimeError(f'Expected dict, got {type(d).__name__}')
    return k in d
def del_(d, k):
    if not isinstance(d, dict):
        raise TinyRuntimeError(f'Expected dict, got {type(d).__name__}')
    if k not in d:
        raise TinyRuntimeError(f'Key {k} not found in dict')
    del d[k]
    return None
