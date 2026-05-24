import sys
import os
sys.path.append('.')
from tinylang.evaluator import run
from tinylang.errors import TinyRuntimeError

source = "break;"
try:
    run(source)
    print("Failed: break should have raised error")
except TinyRuntimeError as e:
    print(f"Passed: caught expected error: {e}")
except Exception as e:
    print(f"Failed: caught wrong exception: {type(e).__name__}: {e}")
except BaseException as e:
    print(f"Failed: caught BaseException: {type(e).__name__}: {e}")
