from tinylang.lexer import tokenize

def test_string_escape():
    # This source string contains a literal backslash and an 'n'
    source = '"hello\\nworld"'
    tokens = tokenize(source)
    print(f"Source: {repr(source)}")
    print(f"Tokens: {tokens}")
    assert tokens[0].value == "hello\nworld"

if __name__ == "__main__":
    test_string_escape()
