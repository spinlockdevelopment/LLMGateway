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
        where = f" at line {self.line}, col {self.col}" if self.line is not None else ""
        return f"{self.message}{where}"

class LexError(TinylangError):
    pass

class ParseError(TinylangError):
    pass

class TinyRuntimeError(TinylangError):
    # has an optional `stack` attribute: a list of frame dicts
    # [{"fn": "<name>", "line": int}, ...] outermost first
    stack: list

    def __init__(self, message, line=None, col=None, stack=None):
        super().__init__(message, line, col)
        self.stack = stack if stack is not None else []

    def traceback(self):
        """Returns a multi-line string of the traceback."""
        res = [str(self)]
        for frame in self.stack:
            res.append(f"  in {frame['fn']} at line {frame['line']}")
        return "\n".join(res)

# For backward compatibility with existing imports
RuntimeError = TinyRuntimeError
