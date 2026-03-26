"""Shared fixtures for LLM Gateway tests."""
import sys
from pathlib import Path

import pytest

# Add scripts/ to sys.path so imports work like they do at runtime
_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))
