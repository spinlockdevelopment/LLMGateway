from tinylang.evaluator import run
import tinylang.builtins

print(f"Builtins: {tinylang.builtins.get_builtins([])}")
print(f"Run result: {repr(run('print(1 + 2);'))}")
