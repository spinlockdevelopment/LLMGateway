from dataclasses import dataclass
from typing import Any, List, Optional, Union, Tuple

@dataclass
class Token:
    kind: str
    value: Any
    line: int
    column: int

@dataclass
class Program:
    statements: List[Any]

class FnDecl:
    def __init__(self, name, params, body):
        self.name = name
        self.params = params
        self.body = body

class FnLit:
    def __init__(self, params, body):
        self.params = params
        self.body = body

class Call:
    def __init__(self, func, args):
        self.func = func
        self.args = args

class ReturnStmt:
    def __init__(self, value):
        self.value = value

@dataclass
class DictLit:
    entries: List[Tuple[Union[str, float], Any]]

class DictGet:
    def __init__(self, dict_expr, key_expr):
        self.dict_expr = dict_expr
        self.key_expr = key_expr

class DictSet:
    def __init__(self, dict_expr, key_expr, value_expr):
        self.dict_expr = dict_expr
        self.key_expr = key_expr
        self.value_expr = value_expr

class ForStmt:
    def __init__(self, var_names: List[str], iterable_expr, body):
        self.var_names = var_names
        self.iterable_expr = iterable_expr
        self.body = body
