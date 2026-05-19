"""Lexical environment for tinylang.

A small chain-of-scopes structure: each :class:`Environment` has an optional
parent and a local ``dict`` of bindings. The evaluator threads instances of
this class through statement execution so that ``let`` introduces a binding in
the *current* scope, plain ``=`` walks up the chain to the nearest enclosing
binding, and a block opens a fresh child scope (phase 4 spec).

This module is intentionally light — later phases (functions, closures, for
loops) reuse the same shape, so its API is small and stable.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class Environment:
    """A single lexical scope, optionally chained to a parent scope."""

    __slots__ = ("parent", "values")

    def __init__(self, parent: Optional["Environment"] = None) -> None:
        self.parent: Optional["Environment"] = parent
        self.values: Dict[str, Any] = {}

    # ------------------------------------------------------------------ define

    def define(self, name: str, value: Any) -> None:
        """Introduce ``name`` in *this* scope.

        Re-declaring the same name at the same scope level is a programmer
        error (phase 4 spec). The caller (evaluator) is expected to translate
        the ``KeyError`` into a tinylang runtime error with a helpful message;
        we raise a plain :class:`KeyError` here to keep this module free of
        evaluator-specific error types.
        """
        if name in self.values:
            raise KeyError(name)
        self.values[name] = value

    # ------------------------------------------------------------------ assign

    def assign(self, name: str, value: Any) -> bool:
        """Walk up the scope chain and rebind the nearest ``name``.

        Returns ``True`` if a binding was found and updated, ``False`` if no
        enclosing scope contains ``name``. Per the phase 4 spec, the caller
        must treat ``False`` as a runtime error (no silent globals).
        """
        env: Optional[Environment] = self
        while env is not None:
            if name in env.values:
                env.values[name] = value
                return True
            env = env.parent
        return False

    # ------------------------------------------------------------------ lookup

    def get(self, name: str) -> Any:
        """Resolve ``name`` against this scope and its ancestors.

        Raises :class:`KeyError` when the name is not bound anywhere in the
        chain; the evaluator turns that into a runtime error.
        """
        env: Optional[Environment] = self
        while env is not None:
            if name in env.values:
                return env.values[name]
            env = env.parent
        raise KeyError(name)

    # ------------------------------------------------------------------ checks

    def has(self, name: str) -> bool:
        """``True`` if ``name`` is bound anywhere up the chain."""
        env: Optional[Environment] = self
        while env is not None:
            if name in env.values:
                return True
            env = env.parent
        return False

    def has_local(self, name: str) -> bool:
        """``True`` if ``name`` is bound directly in this scope."""
        return name in self.values

    # ------------------------------------------------------------------- child

    def child(self) -> "Environment":
        """Open a new scope whose parent is ``self``."""
        return Environment(self)

    # -------------------------------------------------------------------- repr

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"Environment(values={list(self.values)}, parent={'<env>' if self.parent else None})"
