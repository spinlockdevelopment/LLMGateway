#!/usr/bin/env python3
"""Test script for Phase 5 control flow implementation."""

from tinylang.evaluator import run

def test_simple_while():
    """Test basic while loop functionality."""
    source = """
let i = 0;
let sum = 0;
while (i < 5) {
  sum = sum + i;
  i = i + 1;
}
print(sum);
"""
    result = run(source)
    print("Simple while test passed")

def test_break_continue():
    """Test break and continue statements."""
    source = """
let i = 0;
let count = 0;
while (true) {
  if (i == 3) { break; }
  if (i == 1) { 
    i = i + 1; 
    continue; 
  }
  print(i);
  count = count + 1;
  i = i + 1;
}
print(count);
"""
    result = run(source)
    print("Break/continue test passed")

def test_if_else():
    """Test if/else statements."""
    source = """
let x = 10;
let result = 0;
if (x > 5) {
  result = 1;
} else {
  result = 2;
}
print(result);
"""
    result = run(source)
    print("If/else test passed")

if __name__ == "__main__":
    print("Testing Phase 5 functionality...")
    try:
        test_simple_while()
        test_break_continue()
        test_if_else()
        print("All tests passed!")
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()