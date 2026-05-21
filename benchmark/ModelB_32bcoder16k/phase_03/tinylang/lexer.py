from dataclasses import dataclass

class Token:
    def __init__(self, kind: str, value: object, line: int, col: int):
        self.kind = kind
        self.value = value
        self.line = line
        self.col = col

def tokenize(source: str) -> list[Token]:
    return [Token('EOF', None, 1, 1)]
