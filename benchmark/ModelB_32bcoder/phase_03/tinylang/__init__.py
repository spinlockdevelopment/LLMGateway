from dataclasses import dataclass

class Token:
    kind: str
    value: object
    line: int
    col: int


def tokenize(source: str) -> list:
    pass
