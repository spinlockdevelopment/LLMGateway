from tinylang.lexer import tokenize
from tinylang.parser import parse

# Test simple case
try:
    result = parse("let x = 1;")
    print("Success!")
    print(result)
except Exception as e:
    print(f"Error: {e}")
    print(f"Error type: {type(e)}")