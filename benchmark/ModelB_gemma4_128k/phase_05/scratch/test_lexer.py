from tinylang.lexer import tokenize

def test_lexer():
    # Test 1: Basic
    tokens = tokenize("let x = 10;")
    assert tokens[0].kind == "KEYWORD" and tokens[0].value == "let"
    assert tokens[1].kind == "IDENT" and tokens[1].value == "x"
    assert tokens[2].kind == "PUNCT" and tokens[2].value == "="
    assert tokens[3].kind == "NUMBER" and tokens[3].value == 10.0
    assert tokens[4].kind == "PUNCT" and tokens[4].value == ";"
    assert tokens[5].kind == "EOF"

    # Test 2: Floats
    tokens = tokenize("3.14")
    assert tokens[0].kind == "NUMBER" and tokens[0].value == 3.14

    # Test 3: Strings with escapes
    tokens = tokenize('"hello\\nworld"')
    assert tokens[0].kind == "STRING" and tokens[0].value == "hello\nworld"

    # Test 4: Comments
    tokens = tokenize("let x = 1; // comment")
    assert len(tokens) == 6 # let, x, =, 1, ;, EOF

    # Test 5: Multi-char punctuation
    tokens = tokenize("== != <= >= && ||")
    assert tokens[0].kind == "PUNCT" and tokens[0].value == "=="
    assert tokens[1].kind == "PUNCT" and tokens[1].value == "!="
    assert tokens[2].kind == "PUNCT" and tokens[2].value == "<="
    assert tokens[3].kind == "PUNCT" and tokens[3].value == ">="
    assert tokens[4].kind == "PUNCT" and tokens[4].value == "&&"
    assert tokens[5].kind == "PUNCT" and tokens[5].value == "||"

    # Test 6: Error - Unterminated string
    try:
        tokenize('"unterminated')
        assert False, "Should have raised Exception"
    except Exception as e:
        assert "Unterminated string" in str(e)

    # Test 7: Error - Unrecognized character
    try:
        tokenize("@")
        assert False, "Should have raised Exception"
    except Exception as e:
        assert "Unrecognized character" in str(e)

    # Test 8: Error - Unterminated string with newline
    try:
        tokenize('"line1\nline2"')
        assert False, "Should have raised Exception"
    except Exception as e:
        assert "Unterminated string" in str(e)

    # Test 9: Empty input
    tokens = tokenize("")
    assert len(tokens) == 1
    assert tokens[0].kind == "EOF"

    # Test 10: Line and Col tracking
    tokens = tokenize("let\n  x = 1;")
    # let (1,1), \n (2,1), x (2,3), = (2,5), 1 (2,7), ; (2,8), EOF (2,9)
    # Wait, let's check col for x.
    # let (1,1)
    # \n (1,4) -> line 2, col 1
    # space (2,1) -> col 2
    # space (2,2) -> col 3
    # x (2,3)
    assert tokens[0].line == 1 and tokens[0].col == 1
    assert tokens[1].line == 2 and tokens[1].col == 3
    assert tokens[2].line == 2 and tokens[2].col == 5
    assert tokens[3].line == 2 and tokens[3].col == 7
    assert tokens[4].line == 2 and tokens[4].col == 8
    assert tokens[5].line == 2 and tokens[5].col == 9

    print("All tests passed!")

if __name__ == "__main__":
    test_lexer()
