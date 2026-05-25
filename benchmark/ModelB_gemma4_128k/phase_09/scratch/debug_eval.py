from tinylang.evaluator import Evaluator
from tinylang.ast import *

evaluator = Evaluator()
print(f"Eval NumberLit(1.0): {evaluator.evaluate(NumberLit(1.0))}")
print(f"Eval BinaryOp(1.0 + 2.0): {evaluator.evaluate(BinaryOp('+', NumberLit(1.0), NumberLit(2.0)))}")
print(f"Builtins: {evaluator.builtins}")
print(f"Eval Call print(1.0 + 2.0): {evaluator.evaluate(Call(Identifier('print'), [BinaryOp('+', NumberLit(1.0), NumberLit(2.0))]))}")
print(f"Output buffer: {evaluator.output_buffer}")
