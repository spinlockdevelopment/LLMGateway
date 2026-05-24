from tinylang.evaluator import run
print(f"'{run('print(5);')}'")
print(f"'{run('print(1 + 2 * 3);')}'")
print(f"'{run('print(\"hi\" + \" \" + \"you\");')}'")
print(f"'{run('print(true && \"x\");')}'")
