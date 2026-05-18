import io
import sys
import os
import textwrap
from pathlib import Path

import pytest

from tinylang.cli import main


def _write_program(tmp_path: Path, source: str, name: str = "prog.tl") -> Path:
    p = tmp_path / name
    p.write_text(source)
    return p


def test_run_subcommand_prints_output(tmp_path, capsys):
    f = _write_program(tmp_path, 'print("hello");\nprint(1 + 2);\n')
    rc = main(["run", str(f)])
    out = capsys.readouterr()
    assert rc == 0
    assert out.out == "hello\n3\n"


def test_check_subcommand_ok(tmp_path, capsys):
    f = _write_program(tmp_path, "let x = 1; print(x);\n")
    rc = main(["check", str(f)])
    out = capsys.readouterr()
    assert rc == 0
    assert "ok" in out.out.lower()


def test_check_subcommand_parse_error(tmp_path, capsys):
    f = _write_program(tmp_path, "let x = ;\n")
    rc = main(["check", str(f)])
    out = capsys.readouterr()
    assert rc != 0
    assert out.err.strip() != ""


def test_run_missing_file(tmp_path, capsys):
    rc = main(["run", str(tmp_path / "does_not_exist.tl")])
    out = capsys.readouterr()
    assert rc == 2
    assert out.err.strip() != ""


def test_run_runtime_error_nonzero_exit(tmp_path, capsys):
    f = _write_program(tmp_path, "print(missing);\n")
    rc = main(["run", str(f)])
    out = capsys.readouterr()
    assert rc == 1
    assert out.err.strip() != ""


def test_repl_simple_session(monkeypatch, capsys):
    inputs = io.StringIO(textwrap.dedent("""\
    let x = 1;
    let y = 2;
    print(x + y);
    """))
    monkeypatch.setattr("sys.stdin", inputs)
    rc = main(["repl"])
    out = capsys.readouterr()
    assert rc == 0
    # The "3" from print(x+y) must appear in stdout somewhere.
    assert "3" in out.out


def test_repl_preserves_state_across_inputs(monkeypatch, capsys):
    inputs = io.StringIO("let n = 10;\nprint(n);\nn = n + 5;\nprint(n);\n")
    monkeypatch.setattr("sys.stdin", inputs)
    rc = main(["repl"])
    out = capsys.readouterr()
    assert rc == 0
    assert "10" in out.out and "15" in out.out
