from dataclasses import dataclass

@dataclass
class Token:
    kind: str
    value: object
    line: int
    col: int


def tokenize(source: str) -> list[Token]:
    pass
