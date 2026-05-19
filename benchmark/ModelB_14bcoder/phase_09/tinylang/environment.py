from tinylang.ast import *
from tinylang.errors import TinyRuntimeError
from typing import Any, Dict, List, Optional

class Environment:
    def __init__(self, parent: Optional['Environment'] = None):
        self.parent = parent
        self.variables: Dict[str, Any] = {}

    def get(self, name: str) -> Any:
        if name in self.variables:
            return self.variables[name]
        elif self.parent is not None:
            return self.parent.get(name)
        else:
            raise TinyRuntimeError(f'Undefined variable: {name}')

    def set(self, name: str, value: Any) -> None:
        self.variables[name] = value

    def define(self, name: str, value: Any) -> None:
        self.variables[name] = value

    def assign(self, name: str, value: Any) -> None:
        if name in self.variables:
            self.variables[name] = value
        elif self.parent is not None:
            self.parent.assign(name, value)
        else:
            raise TinyRuntimeError(f'Undefined variable: {name}')
