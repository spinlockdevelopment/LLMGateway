from typing import Any, List
from tinylang.ast import *
from tinylang.environment import Environment
from tinylang.errors import TinyRuntimeError
from tinylang.parser import parse

class Function:
    def __init__(self, name: str, parameters: List[str], body: Block, closure_env: Environment):
        self.name = name
        self.parameters = parameters
        self.body = body
        self.closure_env = closure_env  # The environment where the function was defined
    
    def call(self, args: List[Any], env: Environment) -> Any:
        # Check argument count
        if len(args) != len(self.parameters):
            raise TinyRuntimeError(f"Function '{self.name}' expects {len(self.parameters)} arguments, got {len(args)}")
        
        # Create a new environment for the function call
        # The parent environment is the closure environment (where the function was defined)
        child_env = self.closure_env.child()
        
        # Bind parameters to the new environment
        for i, param in enumerate(self.parameters):
            if i < len(args):
                child_env.set(param, args[i])
            else:
                child_env.set(param, None)
        
        # Evaluate the function body
        try:
            result = evaluate(self.body, child_env)
            return result
        except ReturnSignal as rs:
            return rs.value

# Internal exceptions for control flow
class BreakSignal(Exception):
    pass

class ContinueSignal(Exception):
    pass

class ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value

def evaluate(node: Any, env: Environment) -> Any:
    if isinstance(node, Program):
        return _evaluate_program(node, env)
    elif isinstance(node, LetStmt):
        return _evaluate_let_stmt(node, env)
    elif isinstance(node, IfStmt):
        return _evaluate_if_stmt(node, env)
    elif isinstance(node, WhileStmt):
        return _evaluate_while_stmt(node, env)
    elif isinstance(node, BreakStmt):
        raise BreakSignal()
    elif isinstance(node, ContinueStmt):
        raise ContinueSignal()
    elif isinstance(node, Block):
        return _evaluate_block(node, env)
    elif isinstance(node, ExpressionStatement):
        return _evaluate_expression(node.expression, env)
    elif isinstance(node, BinaryExpression):
        return _evaluate_binary_expression(node, env)
    elif isinstance(node, LiteralExpression):
        return node.value
    elif isinstance(node, IdentifierExpression):
        return _evaluate_identifier(node, env)
    elif isinstance(node, CallExpression):
        return _evaluate_call_expression(node, env)
    elif isinstance(node, UnaryExpression):
        return _evaluate_unary_expression(node, env)
    elif isinstance(node, FnDecl):
        return _evaluate_fn_decl(node, env)
    elif isinstance(node, FnLit):
        return _evaluate_fn_lit(node, env)
    elif isinstance(node, ListLit):
        return _evaluate_list_lit(node, env)
    elif isinstance(node, DictLit):
        return _evaluate_dict_lit(node, env)
    elif isinstance(node, Index):
        return _evaluate_index(node, env)
    elif isinstance(node, ForStmt):
        return _evaluate_for_stmt(node, env)
    elif isinstance(node, Assign):
        return _evaluate_assign(node, env)
    elif isinstance(node, ReturnStmt):
        raise ReturnSignal(_evaluate_return_stmt(node, env))
    else:
        raise TinyRuntimeError(f"Unknown node type: {type(node)}")

def _evaluate_program(program: Program, env: Environment) -> Any:
    result = None
    for statement in program.statements:
        result = evaluate(statement, env)
    return result

def _evaluate_let_stmt(stmt: LetStmt, env: Environment) -> Any:
    value = evaluate(stmt.value, env)
    env.set(stmt.name, value)
    return value

def _evaluate_if_stmt(stmt: IfStmt, env: Environment) -> Any:
    condition = evaluate(stmt.condition, env)
    # Check truthiness: nil, false, and 0 are falsy; everything else is truthy
    if condition != None and condition != False and condition != 0:
        return evaluate(stmt.then_branch, env)
    elif stmt.else_branch:
        return evaluate(stmt.else_branch, env)
    return None

def _evaluate_while_stmt(stmt: WhileStmt, env: Environment) -> Any:
    while True:
        try:
            condition = evaluate(stmt.condition, env)
            # Check truthiness: nil, false, and 0 are falsy; everything else is truthy
            if condition != None and condition != False and condition != 0:
                # Create a new environment for the loop body
                child_env = env.child()
                evaluate(stmt.body, child_env)
                # Continue to next iteration
            else:
                # Condition is falsy, exit loop
                break
        except BreakSignal:
            break
        except ContinueSignal:
            # Continue to next iteration
            continue
    return None

def _evaluate_block(block: Block, env: Environment) -> Any:
    result = None
    for statement in block.statements:
        result = evaluate(statement, env)
    return result

def _evaluate_expression(expr: Expression, env: Environment) -> Any:
    return evaluate(expr, env)

def _evaluate_binary_expression(expr: BinaryExpression, env: Environment) -> Any:
    left = evaluate(expr.left, env)
    right = evaluate(expr.right, env)
    
    if expr.operator == '+':
        return left + right
    elif expr.operator == '-':
        return left - right
    elif expr.operator == '*':
        return left * right
    elif expr.operator == '/':
        return left / right
    elif expr.operator == '%':
        return left % right
    elif expr.operator == '==':
        return left == right
    elif expr.operator == '!=':
        return left != right
    elif expr.operator == '<':
        return left < right
    elif expr.operator == '>':
        return left > right
    elif expr.operator == '<=':
        return left <= right
    elif expr.operator == '>=':
        return left >= right
    elif expr.operator == '&&':
        # Short-circuit evaluation
        if left:
            return right
        else:
            return left
    elif expr.operator == '||':
        # Short-circuit evaluation
        if left:
            return left
        else:
            return right
    else:
        raise TinyRuntimeError(f"Unknown binary operator: {expr.operator}")

def _evaluate_unary_expression(node: UnaryExpression, env: Environment) -> Any:
    right = evaluate(node.right, env)
    if node.operator == '-':
        return -right
    elif node.operator == '!':
        return not right
    else:
        raise TinyRuntimeError(f"Unknown unary operator: {node.operator}")

def _evaluate_identifier(node: IdentifierExpression, env: Environment) -> Any:
    # Look up the identifier in the environment
    if env.has(node.name):
        return env.get(node.name)
    else:
        raise TinyRuntimeError(f"Undefined variable: {node.name}")

def _evaluate_call_expression(node: CallExpression, env: Environment) -> Any:
    # Evaluate the callee
    callee = evaluate(node.callee, env)
    
    # Evaluate arguments
    args = []
    for arg in node.arguments:
        args.append(evaluate(arg, env))
    
    # Check if callee is a function
    if not isinstance(callee, Function):
        raise TinyRuntimeError("Cannot call non-function value")
    
    # Call the function
    return callee.call(args, env)

def _evaluate_fn_decl(node: FnDecl, env: Environment) -> Any:
    # Create a function object and bind it to the environment
    func = Function(node.name, node.parameters, node.body, env)
    env.set(node.name, func)
    return func

def _evaluate_fn_lit(node: FnLit, env: Environment) -> Any:
    # Create a function object
    return Function(None, node.parameters, node.body, env)

def _evaluate_index(node: Index, env: Environment) -> Any:
    # Evaluate the target (list) and index
    target = evaluate(node.target, env)
    index = evaluate(node.index, env)
    
    # Check that target is a list
    if not isinstance(target, list):
        raise RuntimeError("Indexing can only be done on lists")
    
    # Check that index is a number
    if not isinstance(index, (int, float)):
        raise RuntimeError("Index must be a number")
    
    # Check that index is an integer (no fractional part)
    if isinstance(index, float) and not index.is_integer():
        raise RuntimeError("Index must be an integer")
    
    # Convert to int
    int_index = int(index)
    
    # Check bounds
    if int_index < 0 or int_index >= len(target):
        raise RuntimeError("List index out of bounds")
    
    # Return the value at the index
    return target[int_index]

def _evaluate_assign(node: Assign, env: Environment) -> Any:
    # Evaluate the right-hand side
    value = evaluate(node.value, env)
    
    # Check if the left-hand side is an identifier or index
    if isinstance(node.name, IdentifierExpression):
        # Simple identifier assignment
        env.set(node.name.name, value)
        return value
    elif isinstance(node.name, Index):
        # Index assignment (like xs[0] = value)
        return _evaluate_assign_index(node.name, value, env)
    else:
        raise RuntimeError("Invalid assignment target")

def _evaluate_assign_index(node: Index, value: Any, env: Environment) -> Any:
    # Evaluate the target (list) and index
    target = evaluate(node.target, env)
    index = evaluate(node.index, env)
    
    # Check that target is a list
    if not isinstance(target, list):
        raise RuntimeError("Indexing can only be done on lists")
    
    # Check that index is a number
    if not isinstance(index, (int, float)):
        raise RuntimeError("Index must be a number")
    
    # Check that index is an integer (no fractional part)
    if isinstance(index, float) and not index.is_integer():
        raise RuntimeError("Index must be an integer")
    
    # Convert to int
    int_index = int(index)
    
    # Check bounds
    if int_index < 0 or int_index >= len(target):
        raise RuntimeError("List index out of bounds")
    
    # Assign the value at the index
    target[int_index] = value
    return value

def _evaluate_return_stmt(node: ReturnStmt, env: Environment) -> Any:
    if node.value is None:
        return None
    return evaluate(node.value, env)

def _evaluate_dict_lit(dict_lit: DictLit, env: Environment) -> Any:
    result = {}
    for pair in dict_lit.pairs:
        key = evaluate(pair.key, env)
        value = evaluate(pair.value, env)
        result[key] = value
    return result

def _evaluate_for_stmt(stmt: ForStmt, env: Environment) -> Any:
    iterable = evaluate(stmt.iterable, env)
    
    # Handle different iteration types
    if isinstance(iterable, list):
        # List iteration
        if len(stmt.variables) == 1:
            # Single variable: for (x) in xs
            var = stmt.variables[0]
            for item in iterable:
                child_env = env.child()
                child_env.set(var, item)
                try:
                    evaluate(stmt.body, child_env)
                except BreakSignal:
                    break
                except ContinueSignal:
                    continue
        elif len(stmt.variables) == 2:
            # Two variables: for (i, x) in xs
            index_var = stmt.variables[0]
            value_var = stmt.variables[1]
            for i, item in enumerate(iterable):
                child_env = env.child()
                child_env.set(index_var, i)
                child_env.set(value_var, item)
                try:
                    evaluate(stmt.body, child_env)
                except BreakSignal:
                    break
                except ContinueSignal:
                    continue
    elif isinstance(iterable, dict):
        # Dict iteration
        if len(stmt.variables) == 2:
            # Two variables: for (k, v) in d
            key_var = stmt.variables[0]
            value_var = stmt.variables[1]
            for key, value in iterable.items():
                child_env = env.child()
                child_env.set(key_var, key)
                child_env.set(value_var, value)
                try:
                    evaluate(stmt.body, child_env)
                except BreakSignal:
                    break
                except ContinueSignal:
                    continue
    return None

import io
import sys
import os
from contextlib import redirect_stdout

def run(source: str) -> str:
    """Run a tinylang program and return captured stdout as a string."""
    # Determine the path to stdlib.tl
    stdlib_path = os.path.join(os.path.dirname(__file__), "..", "stdlib.tl")
    
    # Create a fresh environment
    env = Environment()
    
    # Load and execute stdlib if it exists
    try:
        with open(stdlib_path, 'r') as f:
            stdlib_source = f.read()
            stdlib_program = parse(stdlib_source)
            evaluate(stdlib_program, env)
    except FileNotFoundError:
        # stdlib is optional, proceed without it
        pass
    
    # Parse the user program
    program = parse(source)
    
    # Capture stdout
    f = io.StringIO()
    try:
        with redirect_stdout(f):
            evaluate(program, env)
        return f.getvalue()
    except Exception as e:
        # Re-raise the exception to be caught by tests
        raise e
def _evaluate_list_lit(node: ListLit, env: Environment) -> Any:
    '''Evaluate a list literal.'''
    elements = []
    for element in node.elements:
        elements.append(evaluate(element, env))
    return elements

