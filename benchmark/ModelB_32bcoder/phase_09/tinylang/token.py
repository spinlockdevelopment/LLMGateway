from dataclasses import dataclass
from typing import Any, List, Dict
from tinylang.errors import TinylangError, RuntimeError as TinyRuntimeError

@dataclass
class Token:
    type: str
    value: Any
    line: int
    column: int
