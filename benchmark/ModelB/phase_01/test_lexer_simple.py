#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'phase_01'))

from tinylang.lexer import tokenize

# Test basic functionality
def test_basic():
    # Test empty input
    toks = tokenize("")
    print(f"Empty input tokens: {[(t.kind, t.value) for t in toks]}")
    assert len(toks) == 1 and toks[0].kind == "EOF"
    
    # Test simple expression
    toks = tokenize("let x = 1 + 2;")
    print(f"Simple expression tokens: {[(t.kind, t.value) for t in toks]}")
    
    # Test the expected pattern from the spec
    expected_kinds = ["KEYWORD", "IDENT", "PUNCT", "NUMBER", "PUNCT", "NUMBER", "PUNCT", "EOF"]
    actual_kinds = [t.kind for t in toks]
    print(f"Expected kinds: {expected_kinds}")
    print(f"Actual kinds: {actual_kinds}")
    
    # Check if our implementation matches the expected pattern
    if actual_kinds == expected_kinds:
        print("✓ Basic tokenization works correctly")
    else:
        print("✗ Basic tokenization doesn't match expected pattern")
        
    # Test number parsing
    toks = tokenize("42 3.14")
    nums = [t for t in toks if t.kind == "NUMBER"]
    print(f"Number tokens: {[t.value for t in nums]}")
    
    print("✓ Simple tests completed")

if __name__ == "__main__":
    test_basic()