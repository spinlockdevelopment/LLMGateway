import sys
import io
import pathlib
from tinylang.evaluator import Evaluator
from tinylang.errors import TinylangError, ParseError, TinyRuntimeError
from tinylang.builtins import format_tinylang_value
from tinylang.lexer import tokenize
from tinylang.parser import Parser
from tinylang.ast import ExprStmt

def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv

    # If the first argument is a subcommand, we don't need to prepend 'dummy'
    # because the tests call main(['run', ...]) directly.
    # But if it's called via sys.argv, the first argument is the script name.
    
    # Let's check if argv[0] is a subcommand.
    subcommands = {"run", "check", "repl"}
    if len(argv) > 0 and argv[0] in subcommands:
        # This means argv was passed as ['run', 'file.tl']
        pass
    elif len(argv) > 0 and argv[0] not in subcommands and argv[0] != "dummy":
        # This means argv was passed as ['tinylang_cli.py', 'run', 'file.tl']
        # We should skip the first element.
        argv = argv[1:]

    if len(argv) == 0 or (len(argv) == 1 and argv[0] == "repl"):
        return repl()
    
    if len(argv) < 1:
        return repl()

    subcommand = argv[0]

    if subcommand == "run":
        if len(argv) < 2:
            print("Usage: run <file.tl>", file=sys.stderr)
            return 1
        file_path = pathlib.Path(argv[1])
        if not file_path.exists():
            print(f"Error: File {file_path} not found", file=sys.stderr)
            return 2
        
        try:
            source = file_path.read_text()
            evaluator = Evaluator()
            output = evaluator.run(source)
            print(output, end="")
            return 0
        except TinylangError as e:
            if isinstance(e, TinyRuntimeError):
                print(e.traceback(), file=sys.stderr)
            else:
                print(e, file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Unexpected error: {e}", file=sys.stderr)
            return 1

    elif subcommand == "check":
        if len(argv) < 2:
            print("Usage: check <file.tl>", file=sys.stderr)
            return 1
        file_path = pathlib.Path(argv[1])
        if not file_path.exists():
            print(f"Error: File {file_path} not found", file=sys.stderr)
            return 2
        
        try:
            source = file_path.read_text()
            tokens = tokenize(source)
            parser = Parser(tokens)
            parser.parse()
            print("ok")
            return 0
        except TinylangError as e:
            print(e, file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Unexpected error: {e}", file=sys.stderr)
            return 1

    elif subcommand == "repl":
        return repl()
    
    else:
        print(f"Unknown subcommand: {subcommand}", file=sys.stderr)
        return 1

def is_balanced(text: str) -> bool:
    stack = []
    in_string = False
    string_char = None
    i = 0
    while i < len(text):
        char = text[i]
        if in_string:
            if char == string_char:
                # Check for escape
                escaped = False
                j = i - 1
                while j >= 0 and text[j] == '\\':
                    escaped = not escaped
                    j -= 1
                if not escaped:
                    in_string = False
        else:
            if char in ('"', "'"):
                in_string = True
                string_char = char
            elif char in ('{', '(', '['):
                stack.append(char)
            elif char == '}':
                if not stack or stack.pop() != '{': return False
            elif char == ')':
                if not stack or stack.pop() != '(': return False
            elif char == ']':
                if not stack or stack.pop() != '[': return False
        i += 1
    return len(stack) == 0 and not in_string

def repl() -> int:
    evaluator = Evaluator()
    buffer = []
    
    while True:
        prompt = ">>> " if not buffer else "... "
        try:
            line = input(prompt)
            stripped = line.rstrip()
            ends_with_open = stripped and stripped[-1] in ('{', '(', '[')
            
            buffer.append(line)
            
            if ends_with_open or not is_balanced("\n".join(buffer)):
                continue
            else:
                full_text = "\n".join(buffer)
                try:
                    tokens = tokenize(full_text)
                    parser = Parser(tokens)
                    program = parser.parse()
                    
                    # Clear evaluator's output before running
                    evaluator.output = io.StringIO()
                    
                    for stmt in program.stmts:
                        if isinstance(stmt, ExprStmt):
                            val = evaluator.evaluate_expr(stmt.expr)
                            out = evaluator.output.getvalue()
                            if out:
                                print(out, end="")
                                evaluator.output = io.StringIO()
                            print(format_tinylang_value(val))
                        else:
                            evaluator.evaluate_statement(stmt)
                            out = evaluator.output.getvalue()
                            if out:
                                print(out, end="")
                            evaluator.output = io.StringIO()
                    
                    buffer = []
                except TinylangError as e:
                    print(e, file=sys.stderr)
                    buffer = []
                except Exception as e:
                    print(f"Unexpected error: {e}", file=sys.stderr)
                    buffer = []
        except EOFError:
            return 0
        except Exception as e:
            print(f"Unexpected error: {e}", file=sys.stderr)
            return 1

if __name__ == "__main__":
    sys.exit(main())
