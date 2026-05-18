#!/usr/bin/env python3
"""Shim script to run tinylang CLI."""

import sys
import os

# Add the current directory to Python path so we can import tinylang
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run the main function
from tinylang.cli import main

if __name__ == "__main__":
    sys.exit(main())