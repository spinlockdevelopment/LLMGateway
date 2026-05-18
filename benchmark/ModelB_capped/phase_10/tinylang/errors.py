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

    def traceback(self):
        """Return a multi-line traceback string."""
        lines = [f"{type(self).__name__)}: {self.message}"]
        if self.line:
            lines.append(f"  at line {self.line}, col {self.col}")
        return "\n".join(lines)


class LexError(TinylangError): pass
class ParseError(TinylangError): pass
class TinyRuntimeError(TinylangError):
    # has an optional `stack` attribute: a list of frame dicts
    # [{"fn": "<name>", "line": int}, ...] outermost first
    stack: list

    def traceback(self):
        """Return a multi-line traceback string."""
        lines = [f"{type(self).__name__)}: {self.message}"]
        if self.line:
            lines.append(f"  at line {self.line}, col {self.col}")
        
        # Add stack trace if available
        if hasattr(self, 'stack') and self.stack:
            for frame in self.stack:
                fn_name = frame.get('fn', '<anonymous>')
                line_num = frame.get('line', 0)
                lines.append(f"  in {fn_name} at line {line_num}")
        
        return "\n".join(lines)