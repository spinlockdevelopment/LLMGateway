import pathlib
import io
from tinylang.cli import main

tmp_path = pathlib.Path("debug_tmp")
tmp_path.mkdir(exist_ok=True)
f = tmp_path / "prog.tl"
f.write_text('print("hello");\nprint(1 + 2);\n')

import sys
import contextlib

f_out = io.StringIO()
f_err = io.StringIO()

with contextlib.redirect_stdout(f_out), contextlib.redirect_stderr(f_err):
    rc = main(["run", str(f)])

print(f"RC: {rc}")
print(f"STDOUT: {f_out.getvalue()}")
print(f"STDERR: {f_err.getvalue()}")
