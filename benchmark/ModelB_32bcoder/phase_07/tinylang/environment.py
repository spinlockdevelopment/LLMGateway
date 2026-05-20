from tinylang.ast import *
from tinylang.errors import TinylangError, ParseError, RuntimeError as TinyRuntimeError
from typing import Any, Dict, List, Optional


class Environment:
    def __init__(self, parent: Optional['Environment'] = None):
        self.values: Dict[str, Any] = {}
        self.parent = parent

    def get(self, name: str) -> Any:
        if name in self.values:
            return self.values[name]
        elif self.parent:
            return self.parent.get(name)
        else:
            raise TinyRuntimeError(f'Undefined variable \'{name}\'')