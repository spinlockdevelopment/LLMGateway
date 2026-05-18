from tinylang.lexer import tokenize
from tinylang.parser import Parser

# Test a minimal case
tokens = tokenize('let x = 1;')
print("Tokens:")
for i, t in enumerate(tokens):
    print(f"  {i}: {t.kind} = '{t.value}'")

# Test the parse flow manually
parser = Parser(tokens)
print(f"Initial pos: {parser.pos}")
print(f"Initial token: {parser.peek().kind} = '{parser.peek().value}'")

# Step through parse_statement
print("\n=== Testing parse_statement ===")
token = parser.peek()
print(f"Token kind: {token.kind}")
print(f"Token value: {token.value}")

# This is what parse_statement does:
if token.kind == 'KEYWORD':
    print("Found KEYWORD")
    keyword = token.value
    print(f"Keyword value: {keyword}")
    if keyword == 'let':
        print("About to call advance() to consume 'let'")
        parser.advance()  # This should consume 'let'
        print(f"After advance, pos: {parser.pos}")
        print(f"Token now: {parser.peek().kind} = '{parser.peek().value}'")
        print("About to call parse_let_stmt")
        try:
            result = parser.parse_let_stmt()
            print("Success!")
            print(result)
        except Exception as e:
            print(f"Error in parse_let_stmt: {e}")