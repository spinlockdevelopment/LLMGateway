from tinylang.evaluator import run

def main(argv=None):
    if argv is None:
        import sys
        argv = sys.argv
    if len(argv) < 2:
        print("Usage: python tinylang_cli.py [run|check|repl] [file.tl]", file=sys.stderr)
        return 1

    command = argv[1]
    if command == 'run':
        if len(argv) != 3:
            print("Usage: python tinylang_cli.py run <file.tl>", file=sys.stderr)
            return 1
        file_path = argv[2]
        try:
            with open(file_path, 'r') as file:
                source = file.read()
            output = run(source)
            print(output, end='')
            return 0
        except FileNotFoundError:
            print(f"File not found: {file_path}", file=sys.stderr)
            return 2
        except Exception as e:
            import traceback
            print(traceback.format_exc(), file=sys.stderr)
            return 1

    elif command == 'check':
        if len(argv) != 3:
            print("Usage: python tinylang_cli.py check <file.tl>", file=sys.stderr)
            return 1
        file_path = argv[2]
        try:
            with open(file_path, 'r') as file:
                source = file.read()
            from tinylang.parser import parse
            parse(source)
            print("ok")
            return 0
        except Exception as e:
            print(str(e), file=sys.stderr)
            return 1

    elif command == 'repl':
        import code
        from tinylang.evaluator import global_env
        def repl():
            try:
                while True:
                    try:
                        code.interact(local=global_env)
                    except EOFError:
                        print()  # Clean exit
                        break
            except Exception as e:
                print(str(e), file=sys.stderr)

        repl()
        return 0

    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        return 1
