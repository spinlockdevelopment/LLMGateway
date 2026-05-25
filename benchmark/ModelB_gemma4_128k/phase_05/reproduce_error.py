from tinylang.lexer import tokenize
from tinylang.parser import parse

source = '[1, 2, 3,];'
try:
    p = parse(source)
    print("Success")
    print(p)
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
