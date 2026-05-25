from tinylang.evaluator import Evaluator
from tinylang.ast import *

evaluator = Evaluator()
arg = 3.0
print(f"arg: {arg}, type: {type(arg)}")
formatted_args = []
for arg in [arg]:
    if arg is None:
        formatted_args.append("nil")
    elif isinstance(arg, bool):
        formatted_args.append("true" if arg else "false")
    elif isinstance(arg, (int, float)):
        s = repr(arg)
        print(f"repr(arg): {s}")
        if s.endswith(".0"):
            formatted_args.append(s[:-2])
        else:
            formatted_args.append(s)
    elif isinstance(arg, str):
        formatted_args.append(arg)
    else:
        formatted_args.append(str(arg))
print(f"formatted_args: {formatted_args}")
print(f"result: {' '.join(formatted_args) + '\n'}")
