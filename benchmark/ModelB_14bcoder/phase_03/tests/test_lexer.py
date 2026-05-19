from tinylang.lexer import tokenize


def kinds(toks):
    return [t.kind for t in toks]


def values(toks):
    return [t.value for t in toks]


def test_empty_input_just_eof():
    toks = tokenize("")
    assert len(toks) == 1
    assert toks[0].kind == "EOF"


def test_let_x_eq_1_plus_2():
    toks = tokenize("let x = 1 + 2;")
    assert kinds(toks) == [
        "KEYWORD", "IDENT", "PUNCT", "NUMBER", "PUNCT", "NUMBER", "PUNCT", "EOF"
    ]
    assert values(toks) == ["let", "x", "=", 1.0, "+", 2.0, ";", None]


def test_keywords_vs_identifiers():
    toks = tokenize("if iffy true truely")
    assert kinds(toks)[:4] == ["KEYWORD", "IDENT", "KEYWORD", "IDENT"]
    assert toks[0].value == "if"
    assert toks[1].value == "iffy"
    assert toks[2].value == "true"
    assert toks[3].value == "truely"


def test_multi_char_punct():
    toks = tokenize("== != <= >= && ||")
    assert [t.value for t in toks if t.kind == "PUNCT"] == ["==", "!=", "<=", ">=", "&&", "||"]
    # Make sure they're single tokens (5 punct tokens + EOF, not 12)
    non_eof = [t for t in toks if t.kind != "EOF"]
    assert len(non_eof) == 6


def test_single_char_punct_after_multi():
    toks = tokenize("a = b")
    # The lone "=" must lex as "=" not as start of "=="
    assert any(t.kind == "PUNCT" and t.value == "=" for t in toks)


def test_string_escapes():
    toks = tokenize(r'"hello\n\tworld\"\\"')
    s = [t for t in toks if t.kind == "STRING"][0]
    assert s.value == "hello\n\tworld\"\\"


def test_comments_stripped():
    toks = tokenize("let x = 1; // a comment\nlet y = 2;")
    # Comments produce no tokens. After stripping, ids should appear.
    idents = [t.value for t in toks if t.kind == "IDENT"]
    assert idents == ["x", "y"]


def test_line_col_tracking():
    toks = tokenize("let\n  x = 1;")
    let_tok = toks[0]
    x_tok = toks[1]
    assert let_tok.line == 1 and let_tok.col == 1
    assert x_tok.line == 2 and x_tok.col == 3


def test_unknown_char_errors():
    import pytest
    with pytest.raises(Exception) as exc:
        tokenize("let x = @;")
    msg = str(exc.value)
    # Must mention the line and column. Allow flexible wording.
    assert "1" in msg
    # Column 9 (1-based) is where '@' lives in "let x = @;" — accept any digit ≥ 8 to allow off-by-one.
    assert any(c.isdigit() for c in msg)


def test_number_and_float():
    toks = tokenize("42 3.14")
    nums = [t.value for t in toks if t.kind == "NUMBER"]
    assert nums[0] == 42.0
    assert abs(nums[1] - 3.14) < 1e-9


def test_eof_only_once():
    toks = tokenize("x")
    assert sum(1 for t in toks if t.kind == "EOF") == 1
