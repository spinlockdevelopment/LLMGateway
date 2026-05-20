from dataclasses import dataclass
from typing import Any, List, Dict
from tinylang.errors import TinylangError, RuntimeError as TinyRuntimeError
from tinylang.environment import Environment
from tinylang.ast import Program, FnDecl, FnLit, Call, ReturnStmt, LetStmt, IfStmt, WhileStmt, ForStmt, Block, ExprStmt, BinaryOp, UnaryOp, Identifier, Literal
from tinylang.evaluator import eval_fn_decl, eval_fn_lit, eval_call, eval_return_stmt
from tinylang.evaluator import eval_fn_decl, eval_fn_lit, eval_call, eval_return_stmt


@dataclass
class Function:
    params: List[str]
    body: Any  # AST node for the function body
    env: Environment

    def call(self, args: List[Any]) -> Any:
        if len(args) != len(self.params):
            raise TinyRuntimeError(f"Expected {len(self.params)} arguments, got {len(args)}")
        call_env = Environment(parent=self.env)
        for param, arg in zip(self.params, args):
            call_env.bind(param, arg)
        return self.body.eval(call_env)


def eval_fn_decl(node, env):
    fn_name = node.name
    fn = Function(node.params, node.body, env)
    env.bind(fn_name, fn)


def eval_fn_lit(node, env):
    return Function(node.params, node.body, env)


def eval_call(node, env):
    callee = node.callee.eval(env)
    args = [arg.eval(env) for arg in node.args]
    if isinstance(callee, Function):
        return callee.call(args)
    elif callable(callee):
        return callee(*args)
    else:
        raise TinyRuntimeError(f"Attempted to call a non-function value: {callee}")


def eval_return_stmt(node, env):
    value = node.value.eval(env) if node.value else None
    raise ReturnStmt(value)


class ReturnStmt(Exception):
    def __init__(self, value):
        self.value = value


def run(source: str) -> str:
    from io import StringIO
    import sys
    old_stdout = sys.stdout
    new_stdout = StringIO()
    sys.stdout = new_stdout
    try:
        tokens = tokenize(source)
        program = parse(tokens)
        evaluator = Evaluator()
        evaluator.eval(program)
    finally:
        sys.stdout = old_stdout
    return new_stdout.getvalue()


class Evaluator:
    def __init__(self):
        self.global_env = Environment()
        self.builtins = {
            'print': lambda *args: print(*args),
        }
        for name, value in self.builtins.items():
            self.global_env.bind(name, value)

    def eval(self, program: Program) -> None:
        for statement in program.statements:
            try:
                if isinstance(statement, FnDecl):
                    eval_fn_decl(statement, self.global_env)
                elif isinstance(statement, FnLit):
                    eval_fn_lit(statement, self.global_env)
                elif isinstance(statement, Call):
                    eval_call(statement, self.global_env)
                elif isinstance(statement, ReturnStmt):
                    eval_return_stmt(statement, self.global_env)
                else:
                    statement.eval(self.global_env)
            except ReturnStmt as e:
                return e.value
