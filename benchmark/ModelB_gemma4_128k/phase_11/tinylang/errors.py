class TinylangError(Exception):
    def __init__(self, message: str, line: int | None = None, col: int | None = None):
        super().__init__(message)
        self.message = message
        self.line = line
        self.col = col

    def __str__(self) -> str:
        where = f" at line {self.line}, col {self.col}" if self.line is not None else ""
        return f"{self.message}{where}"

class LexError(TinylangError):
    pass

class ParseError(TinylangError):
    pass

class TinyRuntimeError(TinylangError):
    def __init__(self, message: str, line: int | None = None, col: int | None = None, stack: list | None = None):
        super().__init__(message, line, col)
        self.stack = stack or []

    def traceback(self) -> str:
        where = f" at line {self.line}, col {self.col}" if self.line is not None else ""
        res = [f"RuntimeError: {self.message}{where}"]
        for frame in self.stack:
            res.append(f"  in {frame['fn']} at line {frame['line']}")
        return "\n".join(res)
