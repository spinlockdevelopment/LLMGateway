from tinylang.lexer import tokenize
from tinylang.parser import Parser

# Test a minimal case
tokens = tokenize('let x = 1;')
print("Tokens:")
for i, t in enumerate(tokens):
    print(f"  {i}: {t.kind} = '{t.value}'")

# Test just the first few steps
parser = Parser(tokens)
print(f"Initial token: {parser.peek().kind} = '{parser.peek().value}'")

# Let's manually step through what should happen in parse_statement
token = parser.peek()
print(f"Token kind: {token.kind}")
if token.kind == 'KEYWORD':
    print(f"Keyword value: {token.value}")
    print("Calling parse_let_stmt...")
    # This is where the problem is - we're calling parse_let_stmt
    # but we haven't consumed the 'let' yet!
    # The issue is that parse_let_stmt expects to be called after 'let' is consumed
    
    # Let's try to call parse_let_stmt manually
    try:
        result = parser.parse_let_stmt()
        print("Result:", result)
    except Exception as e:
        print("Error in parse_let_stmt:", e)