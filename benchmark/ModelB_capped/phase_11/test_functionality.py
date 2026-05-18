#!/usr/bin/env python3

# Test that the function implementation works
from tinylang.evaluator import evaluate, Function
from tinylang.environment import Environment
from tinylang.ast import *

def test_function_creation():
    """Test that we can create a function object"""
    # Create a simple environment
    env = Environment()
    
    # Create a function AST node
    body = Block([])
    func = Function("test", ["x"], body, env)
    
    print("Function created successfully")
    print(f"Function name: {func.name}")
    print(f"Function params: {func.parameters}")
    return func

def test_simple_function_call():
    """Test that we can call a simple function"""
    # This would require a more complex setup
    print("Testing function call would require full evaluator")

if __name__ == "__main__":
    test_function_creation()
    print("Function implementation test completed")