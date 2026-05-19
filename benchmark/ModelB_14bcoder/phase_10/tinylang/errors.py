class TinylangError(Exception):
    message: str
    line: int | None
    col: int | None

    def __init__(self, message, line=None, col=None):
        super().__init__(message)
        self.message = message
        self.line = line
        self.col = col

    def __str__(self):
        where = f" at line {self.line}, col {self.col}" if self.line else ""
        return f"{self.message}{where}"

class LexError(TinylangError): pass
class ParseError(TinylangError): pass
class TinyRuntimeError(TinylangError):
    stack: list
