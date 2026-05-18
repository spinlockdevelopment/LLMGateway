from tinylang.lexer import tokenize
from tinylang.parser import Parser

# Let's debug step by step
tokens = tokenize('let x = 1;')
print("Tokens:")
for i, t in enumerate(tokens):
    print(f"  {i}: {t.kind} = '{t.value}'")

print("\nTrying to parse...")
parser = Parser(tokens)
print(f"Initial pos: {parser.pos}")
print(f"Initial token: {parser.peek().kind} = '{parser.peek().value}'")

# Let's manually trace what should happen
try:
    # This should call parse_statement
    result = parser.parse_program()
    print("Success!")
    print(result)
except Exception as e:
    print(f"Error: {e}")