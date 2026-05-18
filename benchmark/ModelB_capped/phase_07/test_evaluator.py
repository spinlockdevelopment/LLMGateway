#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))))

try:
    from tinylang.evaluator import run
    print("Testing evaluator...")
    
    # Test basic functionality
    result = run("print(1 + 2);")
    print(f"Result: {repr(result)}")
    
    result = run('print("hi" + " you");')
    print(f"Result: {repr(result)}")
    
    result = run("print(1 < 2);")
    print(f"Result: {repr(result)}")
    
    result = run("print(true && \"x\");")
    print(f"Result: {repr(result)}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()