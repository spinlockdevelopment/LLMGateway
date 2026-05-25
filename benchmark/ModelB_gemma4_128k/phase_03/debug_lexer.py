from tinylang.lexer import tokenize
source = '[1, 2, 3,]'
tokens = tokenize(source)
for t in tokens:
    print(f"{t.kind}: {t.value}")
