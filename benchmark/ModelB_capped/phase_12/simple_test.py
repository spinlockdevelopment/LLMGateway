#!/usr/bin/env python3

# Simple test to see if we can run basic evaluator
import sys
sys.path.insert(0, '.')

# Test that we can import and run the evaluator
try:
    from tinylang.evaluator import run
    print("Evaluator imported successfully")
    
    # Try a simple case that should work
    result = run('print("hello");')
    print("Basic execution result:", repr(result))
    
except Exception as e:
    print("Error:", e)
    import traceback
    traceback.print_exc()