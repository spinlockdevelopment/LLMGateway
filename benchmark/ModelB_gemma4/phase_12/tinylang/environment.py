from __future__ import annotations
from tinylang.errors import TinyRuntimeError

class Environment:
    def __init__(self, parent: Environment | None = None):
        self.parent = parent
        self.values: dict[str, any] = {}

    def define(self, name: str, value: any):
        if name in self.values:
            raise TinyRuntimeError(f"Redeclaration of '{name}'")
        self.values[name] = value

    def assign(self, name: str, value: any):
        if name in self.values:
            self.values[name] = value
            return
        if self.parent:
            self.parent.assign(name, value)
            return
        raise TinyRuntimeError(f"Undefined variable '{name}'")

    def get(self, name: str):
        if name in self.values:
            return self.values[name]
        if self.parent:
            return self.parent.get(name)
        raise TinyRuntimeError(f"Undefined variable '{name}'")
