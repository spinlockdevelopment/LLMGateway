#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from tinylang.evaluator import run

# Test basic functionality
try:
    result = run('print("hello");')
    print("Success:", repr(result))
except Exception as e:
    print("Error:", e)
    import traceback
    traceback.print_exc()