from dataclasses import dataclass
from typing import Any, List, Dict
from tinylang.errors import TinylangError, RuntimeError as TinyRuntimeError
from tinylang.environment import Environment
from tinylang.evaluator import Function, eval_fn_decl, eval_fn_lit, eval_call, eval_return_stmt

@dataclass
class Token:
    type: str
    value: Any
    line: int
    column: int

@dataclass
class Program:
    statements: List[Any]

@dataclass
class FnDecl:
    name: str
    params: List[str]
    body: Any

    def eval(self, env: Environment) -> None:
        eval_fn_decl(self, env)

@dataclass
class FnLit:
    params: List[str]
    body: Any

    def eval(self, env: Environment) -> Function:
        return eval_fn_lit(self, env)

@dataclass
class Call:
    callee: Any
    args: List[Any]

    def eval(self, env: Environment) -> Any:
        return eval_call(self, env)

@dataclass
class ReturnStmt:
    value: Any

    def eval(self, env: Environment) -> None:
        eval_return_stmt(self, env)

@dataclass
class LetStmt:
    name: str
    value: Any

    def eval(self, env: Environment) -> None:
        env.bind(self.name, self.value.eval(env))

@dataclass
class IfStmt:
    condition: Any
    then_block: Any
    else_block: Any = None

    def eval(self, env: Environment) -> None:
        if self.condition.eval(env):
            self.then_block.eval(env)
        elif self.else_block:
            self.else_block.eval(env)

@dataclass
class WhileStmt:
    condition: Any
    body: Any

    def eval(self, env: Environment) -> None:
        while self.condition.eval(env):
            self.body.eval(env)

@dataclass
class ForStmt:
    var: str
    index_var: str
    iterable: Any
    body: Any

    def eval(self, env: Environment) -> None:
        iterable_value = self.iterable.eval(env)
        for i, value in enumerate(iterable_value):
            env.bind(self.var, value)
            if self.index_var:
                env.bind(self.index_var, i)
            self.body.eval(env)

@dataclass
class Block:
    statements: List[Any]

    def eval(self, env: Environment) -> None:
        block_env = Environment(parent=env)
        for statement in self.statements:
            statement.eval(block_env)

@dataclass
class ExprStmt:
    expr: Any

    def eval(self, env: Environment) -> None:
        self.expr.eval(env)

@dataclass
class Expression:
    pass

@dataclass
class BinaryOp(Expression):
    left: Any
    op: str
    right: Any

    def eval(self, env: Environment) -> Any:
        left_value = self.left.eval(env)
        right_value = self.right.eval(env)
        if self.op == '+':
            return left_value + right_value
        elif self.op == '-':
            return left_value - right_value
        elif self.op == '*':
            return left_value * right_value
        elif self.op == '/':
            return left_value / right_value
        elif self.op == '%':
            return left_value % right_value
        elif self.op == '==':
            return left_value == right_value
        elif self.op == '!=':
            return left_value != right_value
        elif self.op == '<':
            return left_value < right_value
        elif self.op == '>':
            return left_value > right_value
        elif self.op == '<=':
            return left_value <= right_value
        elif self.op == '>=':
            return left_value >= right_value
        elif self.op == '&&':
            return left_value and right_value
        elif self.op == '||':
            return left_value or right_value
        else:
            raise TinylangError(f'Unknown operator: {self.op}')

@dataclass
class UnaryOp(Expression):
    op: str
    operand: Any

    def eval(self, env: Environment) -> Any:
        operand_value = self.operand.eval(env)
        if self.op == '!':
            return not operand_value
        elif self.op == '-':
            return -operand_value
        else:
            raise TinylangError(f'Unknown operator: {self.op}')

@dataclass
class Identifier(Expression):
    name: str

    def eval(self, env: Environment) -> Any:
        return env.lookup(self.name)

@dataclass
class Literal(Expression):
    value: Any

    def eval(self, env: Environment) -> Any:
        return self.value
