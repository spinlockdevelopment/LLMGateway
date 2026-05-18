#!/usr/bin/env python3

# Final test to make sure everything works
import sys
sys.path.insert(0, '.')

# Test the functionality we implemented
try:
    from tinylang.evaluator import run
    
    # Test list literals
    test_code = '''
let xs = [1, 2, 3];
print(xs);
print(xs[0]);
print(len(xs));
push(xs, 4);
print(xs);
xs[1] = 20;
print(xs);
let last = pop(xs);
print(last, xs);
'''
    
    print("Testing list functionality...")
    result = run(test_code)
    print("Result:", repr(result))
    
except Exception as e:
    print("Error:", e)
    import traceback
    traceback.print_exc()