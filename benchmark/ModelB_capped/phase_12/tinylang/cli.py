import sys
import os
from typing import List, Optional

from tinylang.evaluator import run
from tinylang.parser import parse
from tinylang.errors import TinylangError, ParseError, TinyRuntimeError
from tinylang.ast import Program


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point for the tinylang CLI."""
    if argv is None:
        argv = sys.argv[1:]
    
    # Default to REPL if no arguments
    if not argv:
        return repl()
    
    command = argv[0]
    
    if command == "run":
        if len(argv) != 2:
            print("Usage: python tinylang_cli.py run <file.tl>", file=sys.stderr)
            return 2
        return run_file(argv[1])
    
    elif command == "check":
        if len(argv) != 2:
            print("Usage: python tinylang_cli.py check <file.tl>", file=sys.stderr)
            return 2
        return check_file(argv[1])
    
    elif command == "repl":
        return repl()
    
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        print("Available commands: run, check, repl", file=sys.stderr)
        return 1


def run_file(filename: str) -> int:
    """Run a tinylang file."""
    try:
        with open(filename, 'r') as f:
            source = f.read()
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.", file=sys.stderr)
        return 2
    
    try:
        result = run(source)
        print(result, end='')
        return 0
    except TinylangError as e:
        print(str(e), file=sys.stderr)
        if hasattr(e, 'traceback') and e.traceback:
            print(e.traceback(), file=sys.stderr)
        return 1


def check_file(filename: str) -> int:
    """Parse a tinylang file and check for errors."""
    try:
        with open(filename, 'r') as f:
            source = f.read()
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.", file=sys.stderr)
        return 2
    
    try:
        parse(source)
        print("ok")
        return 0
    except ParseError as e:
        print(f"Parse error: {e}", file=sys.stderr)
        return 1


def repl() -> int:
    """Start the REPL."""
    # Create a persistent global environment
    from tinylang.environment import Environment
    from tinylang.builtins import print_func, len_func, push, pop, keys, values, has, del_func
    env = Environment()
    
    # Set up built-in functions in the environment
    env.define("print", print_func)
    env.define("len", len_func)
    env.define("push", push)
    env.define("pop", pop)
    env.define("keys", keys)
    env.define("values", values)
    env.define("has", has)
    env.define("del", del_func)
    
    while True:
        try:
            line = input(">>> ")
            
            # Try to parse and execute the input
            try:
                from tinylang.parser import parse
                from tinylang.evaluator import evaluate
                # Try to parse as expression first
                try:
                    parsed = parse(line)
                    if isinstance(parsed, Program) and len(parsed.statements) == 1:
                        stmt = parsed.statements[0]
                        # If it's an expression statement, evaluate it
                        if hasattr(stmt, 'expression'):
                            result = evaluate(line, env)
                            if result is not None:
                                print(result)
                        else:
                            # Otherwise, execute the statement
                            evaluate(line, env)
                    else:
                        # For multi-statement programs, execute them
                        evaluate(line, env)
                except Exception:
                    # If parsing fails, try to execute as a statement
                    evaluate(line, env)
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
                
        except EOFError:
            # Ctrl-D to exit
            break
        except KeyboardInterrupt:
            # Ctrl-C to exit
            break
    
    return 0