class TinylangError(Exception):
    pass

class ParseError(TinylangError):
    def __init__(self, message, line, col):
        super().__init__(f'Parse error at line {line}, column {col}: {message}')

class RuntimeError(TinylangError):
    def __init__(self, message, line=None, col=None):
        if line is not None and col is not None:
            super().__init__(f'Runtime error at line {line}, column {col}: {message}')
        else:
            super().__init__(f'Runtime error: {message}')

TinyRuntimeError = RuntimeError
