class TinylangError(Exception):
    """Base exception for tinylang errors."""
    pass

class ParseError(TinylangError):
    """Exception for parsing errors."""
    pass

class RuntimeError(TinylangError):
    """Exception for runtime errors."""
    pass