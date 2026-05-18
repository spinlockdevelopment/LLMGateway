import sys
sys.path.insert(0, '.')

# Test just the basic functionality
from tinylang.parser import parse

try:
    result = parse('let x = 1;')
    print("Parse successful!")
    print(f"Result type: {type(result)}")
    print(f"Statements: {result.stmts}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()