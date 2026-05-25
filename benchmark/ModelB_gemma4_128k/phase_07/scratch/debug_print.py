import tinylang.builtins
buf = []
b = tinylang.builtins.get_builtins(buf)
b['print'](1, 2, 3)
print(f"Buffer: {buf}")
