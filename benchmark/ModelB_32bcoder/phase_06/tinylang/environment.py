from dataclasses import dataclass
from typing import Any, List, Dict
from tinylang.errors import TinylangError

@dataclass
class Environment:
    parent: 'Environment' = None
    values: Dict[str, Any] = None

    def __post_init__(self):
        if self.values is None:
            self.values = {}

    def bind(self, name: str, value: Any) -> None:
        self.values[name] = value

    def lookup(self, name: str) -> Any:
        if name in self.values:
            return self.values[name]
        elif self.parent:
            return self.parent.lookup(name)
        else:
            raise TinylangError(f"Undefined variable: {name}")
