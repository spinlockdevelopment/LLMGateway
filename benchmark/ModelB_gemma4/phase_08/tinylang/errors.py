class TinylangError(Exception):
    pass

class ParseError(TinylangError):
    pass

class RuntimeError(TinylangError):
    pass

TinyRuntimeError = RuntimeError
