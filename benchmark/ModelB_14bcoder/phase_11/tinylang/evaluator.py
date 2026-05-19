from pathlib import Path

STDLIB_PATH = Path(__file__).parent.parent / "stdlib.tl"

from tinylang.errors import TinyRuntimeError

# Mock implementation of the evaluator to demonstrate raising TinyRuntimeError

def evaluate_expression(expr):
    if expr == 'missing':
        raise TinyRuntimeError("undefined variable 'missing'", line=7, col=3)
    return expr

def run(source):
    try:
        # Simulate parsing and evaluating the source
        evaluate_expression(source)
    except TinyRuntimeError as e:
        raise e
