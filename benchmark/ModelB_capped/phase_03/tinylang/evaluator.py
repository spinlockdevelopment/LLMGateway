from tinylang.parser import parse
from tinylang.ast import Program, ExpressionStatement, BinaryExpression, UnaryExpression, LiteralExpression, CallExpression
from tinylang.errors import RuntimeError
from tinylang.builtins import print_func

def run(source: str) -> str:
    """Execute tinylang source code and return printed output."""
    # Parse the source
    program = parse(source)
    
    # Capture output
    output = []
    
    def evaluate_expression(expr):
        """Evaluate an expression and return its value."""
        if isinstance(expr, LiteralExpression):
            return expr.value
        elif isinstance(expr, BinaryExpression):
            left = evaluate_expression(expr.left)
            right = evaluate_expression(expr.right)
            
            # Handle arithmetic operations
            if expr.operator == '+':
                # Check if we're doing string concatenation
                if isinstance(left, str) and isinstance(right, str):
                    return left + right
                elif isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left + right
                else:
                    raise RuntimeError("Invalid operation: cannot add " + 
                                     str(type(left).__name__) + " and " + 
                                     str(type(right).__name__))
            elif expr.operator == '-':
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left - right
                else:
                    raise RuntimeError("Invalid operation: cannot subtract " + 
                                     str(type(left).__name__) + " and " + 
                                     str(type(right).__name__))
            elif expr.operator == '*':
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left * right
                else:
                    raise RuntimeError("Invalid operation: cannot multiply " + 
                                     str(type(left).__name__) + " and " + 
                                     str(type(right).__name__))
            elif expr.operator == '/':
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    if right == 0:
                        raise RuntimeError("Division by zero")
                    return left / right
                else:
                    raise RuntimeError("Invalid operation: cannot divide " + 
                                     str(type(left).__name__) + " and " + 
                                     str(type(right).__name__))
            elif expr.operator == '%':
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    if right == 0:
                        raise RuntimeError("Division by zero")
                    return left % right
                else:
                    raise RuntimeError("Invalid operation: cannot modulo " + 
                                     str(type(left).__name__) + " and " + 
                                     str(type(right).__name__))
            elif expr.operator == '==':
                return left == right
            elif expr.operator == '!=':
                return left != right
            elif expr.operator == '<':
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left < right
                elif isinstance(left, str) and isinstance(right, str):
                    return left < right
                else:
                    raise RuntimeError("Invalid comparison: cannot compare " + 
                                     str(type(left).__name__) + " and " + 
                                     str(type(right).__name__))
            elif expr.operator == '>':
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left > right
                elif isinstance(left, str) and isinstance(right, str):
                    return left > right
                else:
                    raise RuntimeError("Invalid comparison: cannot compare " + 
                                     str(type(left).__name__) + " and " + 
                                     str(type(right).__name__))
            elif expr.operator == '<=':
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left <= right
                elif isinstance(left, str) and isinstance(right, str):
                    return left <= right
                else:
                    raise RuntimeError("Invalid comparison: cannot compare " + 
                                     str(type(left).__name__) + " and " + 
                                     str(type(right).__name__))
            elif expr.operator == '>=':
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left >= right
                elif isinstance(left, str) and isinstance(right, str):
                    return left >= right
                else:
                    raise RuntimeError("Invalid comparison: cannot compare " + 
                                     str(type(left).__name__) + " and " + 
                                     str(type(right).__name__))
            elif expr.operator == '&&':
                # Short-circuit evaluation
                if is_truthy(left):
                    return right
                else:
                    return left
            elif expr.operator == '||':
                # Short-circuit evaluation
                if is_truthy(left):
                    return left
                else:
                    return right
            else:
                raise RuntimeError("Unknown operator: " + expr.operator)
        elif isinstance(expr, UnaryExpression):
            right = evaluate_expression(expr.right)
            if expr.operator == '-':
                if isinstance(right, (int, float)):
                    return -right
                else:
                    raise RuntimeError("Invalid operation: cannot negate " + 
                                     str(type(right).__name__))
            elif expr.operator == '!':
                return not is_truthy(right)
            else:
                raise RuntimeError("Unknown unary operator: " + expr.operator)
        elif isinstance(expr, CallExpression):
            # Handle built-in function calls
            if isinstance(expr.callee, LiteralExpression) and expr.callee.value == 'print':
                # Call the print function
                result = print_func(*[evaluate_expression(arg) for arg in expr.arguments])
                output.append(result)
                return result
            else:
                raise RuntimeError("Unknown function call")
        else:
            raise RuntimeError("Unknown expression type")
    
    def is_truthy(value):
        """Determine if a value is truthy according to tinylang rules."""
        if value is None or value is False or value == 0:
            return False
        return True
    
    # Evaluate all statements
    for statement in program.statements:
        if isinstance(statement, ExpressionStatement):
            evaluate_expression(statement.expression)
    
    # Return the captured output
    return "".join(output)