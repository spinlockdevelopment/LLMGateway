from tinylang.lexer import tokenize
from tinylang.parser import Parser

# Test a minimal case
tokens = tokenize('let x = 1;')
print("Tokens:")
for i, t in enumerate(tokens):
    print(f"  {i}: {t.kind} = '{t.value}'")

# Test the exact sequence
parser = Parser(tokens)
print(f"\nInitial: pos={parser.pos}, token={parser.peek().kind} = '{parser.peek().value}'")

# Step 1: parse_statement sees KEYWORD 'let'
print("\nStep 1: parse_statement sees KEYWORD 'let'")
print(f"Token: {parser.peek().kind} = '{parser.peek().value}'")

# Step 2: parse_statement calls advance() to consume 'let'
print("\nStep 2: parse_statement calls advance() to consume 'let'")
parser.advance()
print(f"After advance: pos={parser.pos}, token={parser.peek().kind} = '{parser.peek().value}'")

# Step 3: parse_let_stmt is called
print("\nStep 3: parse_let_stmt called")
print("parse_let_stmt tries to consume IDENT 'x'")
try:
    identifier = parser.consume('IDENT', "Expected identifier after 'let'")
    print(f"Got identifier: {identifier.value}")
    print(f"Current pos: {parser.pos}")
    print(f"Current token: {parser.peek().kind} = '{parser.peek().value}'")
    
    print("Now trying to consume '='")
    equals = parser.consume('=', "Expected '=' after identifier")
    print(f"Got equals: {equals.value}")
    
except Exception as e:
    print(f"Error: {e}")
    print(f"Current pos: {parser.pos}")
    print(f"Current token: {parser.peek().kind} = '{parser.peek().value}'")