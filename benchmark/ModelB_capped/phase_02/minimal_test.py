import sys
sys.path.insert(0, '.')

# Test just the lexer to make sure it works
from tinylang.lexer import tokenize

tokens = tokenize('let x = 1;')
print("Tokens:")
for i, token in enumerate(tokens):
    print(f"  {i}: {token.kind} = {repr(token.value)}")

# Test if we can import the parser
try:
    from tinylang.parser import parse
    print("Parser imported successfully")
except Exception as e:
    print(f"Parser import failed: {e}")