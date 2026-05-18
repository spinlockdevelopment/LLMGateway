#!/usr/bin/env python3

# Let me create a minimal working parser to test the basic functionality
import sys
sys.path.insert(0, '.')

# Import what we need
from tinylang.ast import *
from tinylang.lexer import tokenize

# Test the lexer first
tokens = tokenize('let x = 1;')
print("Tokens:")
for i, token in enumerate(tokens):
    print(f"  {i}: {token.kind} = {repr(token.value)}")

# Test basic parsing
try:
    from tinylang.parser import parse
    result = parse('let x = 1;')
    print("SUCCESS: Parse completed")
    print(f"Result: {result}")
except Exception as e:
    print(f"FAILED: {e}")
    import traceback
    traceback.print_exc()