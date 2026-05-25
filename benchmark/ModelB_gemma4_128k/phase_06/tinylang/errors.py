class TinylangError(Exception):
    pass

class ParseError(TinylangError):
    def __init__(self, message: str, line: int, col: int):
        self.message = message
        self.line = line
        self.col = col
        super().__init__(f"{message} at line {line}, col {col}")

class RuntimeError(TinylangError):
    pass
