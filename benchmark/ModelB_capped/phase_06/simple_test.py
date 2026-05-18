#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Test the evaluator functionality
try:
    from tinylang.evaluator import run
    print("Evaluator imported successfully")
    
    # Test basic print
    result = run("print(1 + 2);")
    print(f"Result: {repr(result)}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()