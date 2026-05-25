from tinylang.evaluator import run

def test():
    print(f"'{run('print(1 + 2);')}'")
    assert run("print(1 + 2);") == "3\n"
    print(f"'{run('print(\"hi\" + \" you\");')}'")
    assert run("print(\"hi\" + \" you\");") == "hi you\n"
    print(f"'{run('print(1 < 2);')}'")
    assert run("print(1 < 2);") == "true\n"
    print(f"'{run('print(true && \"x\");')}'")
    assert run("print(true && \"x\");") == "x\n"
    print(f"'{run('print(false || \"y\");')}'")
    assert run("print(false || \"y\");") == "y\n"
    print(f"'{run('print(10 / 2);')}'")
    assert run("print(10 / 2);") == "5\n"
    print(f"'{run('print(10 / 4);')}'")
    assert run("print(10 / 4);") == "2.5\n"
    print(f"'{run('print(10 % 3);')}'")
    assert run("print(10 % 3);") == "1\n"
    print(f"'{run('print(10 - 3);')}'")
    assert run("print(10 - 3);") == "7\n"
    print(f"'{run('print(10 * 3);')}'")
    assert run("print(10 * 3);") == "30\n"
    print(f"'{run('print(10 == 10);')}'")
    assert run("print(10 == 10);") == "true\n"
    print(f"'{run('print(10 != 10);')}'")
    assert run("print(10 != 10);") == "false\n"
    print(f"'{run('print(\"a\" == \"a\");')}'")
    assert run("print(\"a\" == \"a\");") == "true\n"
    print(f"'{run('print(\"a\" != \"b\");')}'")
    assert run("print(\"a\" != \"b\");") == "true\n"
    print(f"'{run('print(\"a\" < \"b\");')}'")
    assert run("print(\"a\" < \"b\");") == "true\n"
    print(f"'{run('print(\"b\" < \"a\");')}'")
    assert run("print(\"b\" < \"a\");") == "false\n"
    
    try:
        run("print(2 / 0);")
    except Exception as e:
        assert "Division by zero" in str(e)
    
    try:
        run("print(1 + \"a\");")
    except Exception as e:
        assert "Type error" in str(e)

    try:
        run("print(1 < \"a\");")
    except Exception as e:
        assert "Type error" in str(e)

    print("All tests passed!")

if __name__ == "__main__":
    test()
