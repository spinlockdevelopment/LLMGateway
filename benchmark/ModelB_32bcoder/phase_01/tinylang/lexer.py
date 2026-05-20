from dataclasses import dataclass

class Token:
    kind: str
    value: object
    line: int
    col: int

    def __init__(self, kind, value, line, col):
        self.kind = kind
        self.value = value
        self.line = line
        self.col = col


def tokenize(source: str) -> list:
    tokens = []
    i = 0
    line = 1
    col = 1
    while i < len(source):
        char = source[i]
        if char.isspace():
            if char == '\n':
                line += 1
                col = 1
            else:
                col += 1
            i += 1
        elif char == '/' and i + 1 < len(source) and source[i + 1] == '/':
            while i < len(source) and source[i] != '\n':
                i += 1
            i += 1  # Skip the newline character
        else:
            raise Exception(f"Unexpected character '{char}' at line {line}, column {col}")
    tokens.append(Token('EOF', None, line, col))
    return tokens
