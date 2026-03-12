"""
Shared console output helpers for LLM Gateway CLI tools.

Provides clean, colored terminal output with NO timestamps or log levels.
Warnings print in yellow, errors in red, success in green.

Zero external dependencies — safe to import from system Python (no venv).
"""

from __future__ import annotations

import os
import sys


# ── Color support detection ──────────────────────────────────────────────────

def _supports_color() -> bool:
    """Check if the terminal supports ANSI color codes."""
    if os.environ.get("NO_COLOR"):
        return False
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


_COLOR = _supports_color()

# ANSI escape codes
_RED = "\033[0;31m"
_GREEN = "\033[0;32m"
_YELLOW = "\033[1;33m"
_CYAN = "\033[0;36m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_NC = "\033[0m"  # reset


def _c(code: str, text: str) -> str:
    """Wrap text in an ANSI color code if color is supported."""
    return f"{code}{text}{_NC}" if _COLOR else text


# ── Color wrappers (return strings, don't print) ────────────────────────────

def bold(text: str) -> str:
    return _c(_BOLD, text)

def dim(text: str) -> str:
    return _c(_DIM, text)

def green(text: str) -> str:
    return _c(_GREEN, text)

def red(text: str) -> str:
    return _c(_RED, text)

def yellow(text: str) -> str:
    return _c(_YELLOW, text)

def cyan(text: str) -> str:
    return _c(_CYAN, text)


# ── Print helpers (print directly, no timestamps, no log levels) ─────────────

def info(msg: str = "") -> None:
    """Print plain text."""
    print(msg)


def success(msg: str) -> None:
    """Print with green checkmark prefix."""
    print(f"  {green('✓')} {msg}")


def warn(msg: str) -> None:
    """Print with yellow warning prefix — stands out clearly."""
    print(f"  {yellow('⚠ Warning:')} {msg}")


def error(msg: str) -> None:
    """Print with red error prefix — stands out clearly."""
    print(f"  {red('✗ Error:')} {msg}")


# ── Structure helpers ────────────────────────────────────────────────────────

def heading(title: str) -> None:
    """Print a bold section heading with blank line above."""
    print(f"\n  {bold(title)}")


def separator(width: int = 88) -> None:
    """Print a horizontal rule."""
    print(f"  {'─' * width}")


def blank() -> None:
    """Print a blank line."""
    print()


def banner(title: str) -> None:
    """Print a prominent section banner (setup phases, etc.)."""
    bar = "=" * 56
    print(f"\n  {bar}")
    print(f"  {bold(title)}")
    print(f"  {bar}")


# ── Interactive prompts ──────────────────────────────────────────────────────

def is_interactive() -> bool:
    """Return True if stdin is a TTY (user can answer prompts)."""
    try:
        return sys.stdin.isatty()
    except Exception:
        return False


def prompt_yes_no(question: str, default: bool = True) -> bool:
    """
    Ask a yes/no question. Returns the default if input is empty or non-interactive.
    """
    suffix = " [Y/n]: " if default else " [y/N]: "
    if not is_interactive():
        return default
    try:
        answer = input(question + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    if not answer:
        return default
    return answer in ("y", "yes")


def prompt_input(label: str, default: str = "") -> str:
    """
    Prompt for a text value. Shows default in brackets. Returns default if empty.
    """
    if default:
        display = f"  {label} [{default}]: "
    else:
        display = f"  {label}: "
    if not is_interactive():
        return default
    try:
        value = input(display).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    return value if value else default


def prompt_secret(label: str, default: str = "") -> str:
    """
    Prompt for a secret value (API key, password). Shows masked default if present.
    """
    if default:
        masked = default[:4] + "..." + default[-4:] if len(default) > 8 else "****"
        display = f"  {label} [{masked}]: "
    else:
        display = f"  {label}: "
    if not is_interactive():
        return default
    try:
        value = input(display).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    return value if value else default
