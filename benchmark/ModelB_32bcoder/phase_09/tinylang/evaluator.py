from tinylang.ast import Program, FnDecl, FnLit, Call, ReturnStmt, DictLit, DictGet, DictSet, ForStmt
from tinylang.builtins import keys, values, has, del_
from tinylang.environment import Environment
from tinylang.errors import TinyRuntimeError

def evaluate_expression(node, env):
    if isinstance(node, DictLit):
        return evaluate_dict_lit(node, env)
    elif isinstance(node, DictGet):
        return evaluate_dict_get(node, env)
    elif isinstance(node, DictSet):
        evaluate_dict_set(node, env)
    elif isinstance(node, ForStmt):
        evaluate_for_stmt(node, env)
    else:
        raise NotImplementedError(f'Evaluation of {type(node).__name__} not implemented')

def evaluate_statements(statements, env):
    for statement in statements:
        evaluate_expression(statement, env)

def evaluate_dict_lit(node: DictLit, env: Environment) -> dict:
    result = {}
    for key_expr, value_expr in node.entries:
        key = evaluate_expression(key_expr, env)
        value = evaluate_expression(value_expr, env)
        result[key] = value
    return result

def evaluate_dict_get(node: DictGet, env: Environment) -> Any:
    dict_value = evaluate_expression(node.dict_expr, env)
    key_value = evaluate_expression(node.key_expr, env)
    if not isinstance(dict_value, dict):
        raise TinyRuntimeError(f'Expected dict, got {type(dict_value).__name__}')
    if key_value not in dict_value:
        raise TinyRuntimeError(f'Key {key_value} not found in dict')
    return dict_value[key_value]

def evaluate_dict_set(node: DictSet, env: Environment) -> None:
    dict_value = evaluate_expression(node.dict_expr, env)
    key_value = evaluate_expression(node.key_expr, env)
    value_value = evaluate_expression(node.value_expr, env)
    if not isinstance(dict_value, dict):
        raise TinyRuntimeError(f'Expected dict, got {type(dict_value).__name__}')
    dict_value[key_value] = value_value

def evaluate_for_stmt(node: ForStmt, env: Environment) -> None:
    iterable_value = evaluate_expression(node.iterable_expr, env)
    if not isinstance(iterable_value, (list, dict)):
        raise TinyRuntimeError(f'Expected list or dict, got {type(iterable_value).__name__}')
    if isinstance(iterable_value, list):
        if len(node.var_names) == 1:
            for i, value in enumerate(iterable_value):
                with env.extend({node.var_names[0]: value}):
                    evaluate_statements(node.body, env)
        elif len(node.var_names) == 2:
            for i, value in enumerate(iterable_value):
                with env.extend({node.var_names[0]: i, node.var_names[1]: value}):
                    evaluate_statements(node.body, env)
        else:
            raise TinyRuntimeError(f'Expected 1 or 2 variable names for list iteration, got {len(node.var_names)}')
    elif isinstance(iterable_value, dict):
        if len(node.var_names) == 2:
            for key, value in iterable_value.items():
                with env.extend({node.var_names[0]: key, node.var_names[1]: value}):
                    evaluate_statements(node.body, env)
        else:
            raise TinyRuntimeError(f'Expected 2 variable names for dict iteration, got {len(node.var_names)}')
