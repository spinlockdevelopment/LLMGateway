from tinylang.parser import parse


def names_of(stmts):
    return [type(s).__name__ for s in stmts]


def test_let_stmt():
    p = parse("let x = 1;")
    assert names_of(p.stmts) == ["LetStmt"]
    ls = p.stmts[0]
    assert ls.name == "x"
    assert type(ls.value).__name__ == "NumberLit"
    assert ls.value.value == 1.0


def test_precedence_mul_before_add():
    p = parse("let x = 1 + 2 * 3;")
    rhs = p.stmts[0].value
    assert type(rhs).__name__ == "BinaryOp"
    assert rhs.op == "+"
    # Left is 1, right is 2*3
    assert type(rhs.left).__name__ == "NumberLit"
    assert type(rhs.right).__name__ == "BinaryOp"
    assert rhs.right.op == "*"


def test_comparison_and_logical():
    p = parse("x = 1 < 2 && y;")
    a = p.stmts[0].expr
    assert type(a).__name__ == "Assign"
    rhs = a.value
    assert type(rhs).__name__ == "BinaryOp"
    assert rhs.op == "&&"
    assert type(rhs.left).__name__ == "BinaryOp" and rhs.left.op == "<"


def test_if_else():
    p = parse("if (x) { let a = 1; } else { let b = 2; }")
    s = p.stmts[0]
    assert type(s).__name__ == "IfStmt"
    assert type(s.then_block).__name__ == "Block"
    assert s.else_block is not None


def test_while_with_break_continue():
    p = parse("while (x) { break; continue; }")
    w = p.stmts[0]
    assert type(w).__name__ == "WhileStmt"
    body_stmts = w.body.stmts
    assert names_of(body_stmts) == ["BreakStmt", "ContinueStmt"]


def test_fn_decl_is_fndecl_not_letstmt():
    p = parse("fn add(a, b) { return a + b; }")
    s = p.stmts[0]
    assert type(s).__name__ == "FnDecl"
    assert s.name == "add"
    assert s.params == ["a", "b"]
    body = s.body.stmts
    assert type(body[0]).__name__ == "ReturnStmt"


def test_fn_lit_in_let():
    p = parse("let f = fn(x) { return x; };")
    rhs = p.stmts[0].value
    assert type(rhs).__name__ == "FnLit"
    assert rhs.params == ["x"]


def test_list_and_dict_literals():
    p = parse('let xs = [1, 2, 3,]; let d = {"a": 1, "b": 2};')
    xs = p.stmts[0].value
    d = p.stmts[1].value
    assert type(xs).__name__ == "ListLit"
    assert len(xs.items) == 3
    assert type(d).__name__ == "DictLit"
    assert len(d.pairs) == 2


def test_call_and_index_chain():
    p = parse("f(1, 2)[0];")
    expr = p.stmts[0].expr
    assert type(expr).__name__ == "Index"
    assert type(expr.target).__name__ == "Call"


def test_assign_to_index():
    p = parse("xs[1] = 9;")
    a = p.stmts[0].expr
    assert type(a).__name__ == "Assign"
    assert type(a.target).__name__ == "Index"


def test_invalid_assign_target_raises():
    import pytest
    with pytest.raises(Exception):
        parse("1 = 2;")


def test_for_stmt_one_and_two_names():
    p1 = parse("for (x) in xs { }")
    p2 = parse("for (k, v) in d { }")
    f1 = p1.stmts[0]
    f2 = p2.stmts[0]
    assert type(f1).__name__ == "ForStmt"
    assert f1.names == ["x"]
    assert f2.names == ["k", "v"]


def test_else_if_chain_parses():
    p = parse("if (a) { } else if (b) { } else { }")
    s = p.stmts[0]
    assert type(s).__name__ == "IfStmt"
    # else_block holds either an IfStmt directly or a Block containing one
    eb = s.else_block
    assert eb is not None
    # walk into it
    inner = eb if type(eb).__name__ == "IfStmt" else eb.stmts[0]
    assert type(inner).__name__ == "IfStmt"
