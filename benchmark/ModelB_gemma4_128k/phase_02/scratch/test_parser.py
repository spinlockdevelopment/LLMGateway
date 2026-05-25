from tinylang.parser import parse
from tinylang.ast import *

def test_parser():
    # 1. fn declaration sugar
    prog = parse("fn f(a, b) { return a + b; }")
    assert isinstance(prog.stmts[0], FnDecl)
    assert prog.stmts[0].name == "f"
    assert prog.stmts[0].params == ["a", "b"]
    assert isinstance(prog.stmts[0].body.stmts[0], ReturnStmt)

    # 2. if-else if-else
    prog = parse("if (true) { print(1); } else if (false) { print(2); } else { print(3); }")
    assert isinstance(prog.stmts[0], IfStmt)
    # else_block can be a Block or an IfStmt.
    # In my parser, else if produces a nested IfStmt.
    # If it's an IfStmt, it doesn't have .stmts.
    # If it's a Block, it has .stmts.
    
    # Let's check the structure:
    # IfStmt(cond=true, then_block=Block, else_block=IfStmt(cond=false, then_block=Block, else_block=Block))
    
    else_if = prog.stmts[0].else_block
    assert isinstance(else_if, IfStmt)
    assert isinstance(else_if.then_block, Block)
    assert isinstance(else_if.else_block, Block)

    # 3. for loop
    prog = parse("for (i, v) in [1, 2] { print(i, v); }")
    assert isinstance(prog.stmts[0], ForStmt)
    assert prog.stmts[0].names == ["i", "v"]

    # 4. while loop
    prog = parse("while (true) { break; }")
    assert isinstance(prog.stmts[0], WhileStmt)

    # 5. list and dict literals with trailing commas
    prog = parse("[1, 2, 3,]")
    assert isinstance(prog.stmts[0], ExprStmt)
    assert isinstance(prog.stmts[0].expr, ListLit)
    assert len(prog.stmts[0].expr.items) == 3

    prog = parse("{\"a\": 1, \"b\": 2,}")
    assert isinstance(prog.stmts[0], ExprStmt)
    assert isinstance(prog.stmts[0].expr, DictLit)
    assert len(prog.stmts[0].expr.pairs) == 2

    # 6. assignment with Index
    prog = parse("xs[0] = 10;")
    assert isinstance(prog.stmts[0], ExprStmt)
    assert isinstance(prog.stmts[0].expr, Assign)
    assert isinstance(prog.stmts[0].expr.target, Index)

    # 7. assignment with Identifier
    prog = parse("x = 10;")
    assert isinstance(prog.stmts[0], ExprStmt)
    assert isinstance(prog.stmts[0].expr, Assign)
    assert isinstance(prog.stmts[0].expr.target, Identifier)

    # 8. assignment with invalid target
    try:
        parse("1 = 10;")
        assert False, "Should have raised ParseError"
    except Exception as e:
        print(f"Caught expected error: {e}")

    # 9. assignment with invalid target (call)
    try:
        parse("f() = 10;")
        assert False, "Should have raised ParseError"
    except Exception as e:
        print(f"Caught expected error: {e}")

    # 10. assignment with Index
    prog = parse("xs[0][1] = 5;")
    assert isinstance(prog.stmts[0], ExprStmt)
    assert isinstance(prog.stmts[0].expr, Assign)
    assert isinstance(prog.stmts[0].expr.target, Index)
    assert isinstance(prog.stmts[0].expr.target.target, Index)

    print("All tests passed!")

if __name__ == "__main__":
    test_parser()
