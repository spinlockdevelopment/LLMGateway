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
        
        # Let's manually step through parse_let_stmt
        print("Manual parse_let_stmt:")
        print("  About to call consume('IDENT', 'Expected identifier after let')")
        try:
            identifier = parser.consume('IDENT', "Expected identifier after 'let'")
            print(f"  Got identifier: {identifier.value}")
            print(f"  Current pos: {parser.pos}")
            print(f"  Current token: {parser.peek().kind} = '{parser.peek().value}'")
            print("  About to consume '='")
            equals_token = parser.consume('=', "Expected '=' after identifier")
            print(f"  Got equals: {equals_token.value}")
            print("  About to parse expression")
            # This is where it fails - let's see what happens
            expr = parser.parse_expression()
            print(f"  Got expression: {expr}")
            print("  About to consume ';'")
            semicolon = parser.consume(';', "Expected ';' after let statement")
            print(f"  Got semicolon: {semicolon.value}")
            print("  All done!")
        except Exception as e:
            print(f"Error: {e}")
            print(f"Error type: {type(e)}")
            print(f"Current pos: {parser.pos}")
            print(f"Current token: {parser.peek().kind} = '{parser.peek().value}'")