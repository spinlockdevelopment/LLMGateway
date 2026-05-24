import io
import sys
from tinylang.cli import main

def test_run_subcommand_prints_output(tmp_path, capsys):
    f = tmp_path / "prog.tl"
    f.write_text('print("hello");\nprint(1 + 2);\n')
    rc = main(["run", str(f)])
    out = capsys.readouterr()
    assert rc == 0
    assert out.out == "hello\n3\n"

def test_check_subcommand_ok(tmp_path, capsys):
    f = tmp_path / "prog.tl"
    f.write_text("let x = 1; print(x);\n")
    rc = main(["check", str(f)])
    out = capsys.readouterr()
    assert rc == 0
    assert "ok" in out.out.lower()

def test_run_missing_file(tmp_path, capsys):
    rc = main(["run", str(tmp_path / "does_not_exist.tl")])
    out = capsys.readouterr()
    assert rc == 2
    assert out.err.strip() != ""

def test_repl_simple_session(monkeypatch, capsys):
    inputs = io.StringIO("let x = 1;\nlet y = 2;\nprint(x + y);\n")
    monkeypatch.setattr("sys.stdin", inputs)
    rc = main(["repl"])
    out = capsys.readouterr()
    assert rc == 0
    assert "3" in out.out

def test_repl_preserves_state_across_inputs(monkeypatch, capsys):
    inputs = io.StringIO("let n = 10;\nprint(n);\nn = n + 5;\nprint(n);\n")
    monkeypatch.setattr("sys.stdin", inputs)
    rc = main(["repl"])
    out = capsys.readouterr()
    assert rc == 0
    assert "10" in out.out and "15" in out.out
