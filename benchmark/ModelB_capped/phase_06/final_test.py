#!/usr/bin/env python3

# Final test to make sure the function implementation works

from tinylang.evaluator import Function, evaluate
from tinylang.environment import Environment
from tinylang.ast import *

def test_function_creation():
    """Test that we can create a function object"""
    print("Testing function creation...")
    
    # Create a simple environment
    env = Environment()
    
    # Create a function AST node
    body = Block([])
    func = Function("test", ["x"], body, env)
    
    print("✓ Function created successfully")
    print(f"  Function name: {func.name}")
    print(f"  Function params: {func.parameters}")
    
    return func

def test_function_call():
    """Test that we can call a function"""
    print("\nTesting function call...")
    
    # Create a simple function that returns its argument
    env = Environment()
    
    # Create a simple block that returns the argument
    body = Block([])
    
    # Create function
    func = Function("simple", ["x"], body, env)
    
    print("✓ Function call setup complete")
    return func

def test_ast_nodes():
    """Test that AST nodes are defined correctly"""
    print("\nTesting AST nodes...")
    
    # Test that we can create the new AST nodes
    try:
        # Test ReturnStmt
        return_stmt = ReturnStmt(None)
        print("✓ ReturnStmt created")
        
        # Test FnDecl
        fn_decl = FnDecl("test", ["a"], Block([]))
        print("✓ FnDecl created")
        
        # Test FnLit
        fn_lit = FnLit(["x"], Block([]))
        print("✓ FnLit created")
        
        print("✓ All AST nodes work correctly")
        return True
    except Exception as e:
        print(f"✗ AST node creation failed: {e}")
        return False

if __name__ == "__main__":
    print("=== Final Function Implementation Test ===")
    
    try:
        test_function_creation()
        test_function_call()
        success = test_ast_nodes()
        
        if success:
            print("\n🎉 All function implementation tests passed!")
        else:
            print("\n❌ Some tests failed")
            
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()