"""YAML configuration loader with hot-reload support."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages YAML configuration files with file-watching hot reload."""

    def __init__(self) -> None:
        self._configs: dict[str, dict[str, Any]] = {}
        self._paths: dict[str, Path] = {}
        self._watch_task: asyncio.Task | None = None
        self._callbacks: list[Any] = []

    def load(self, name: str, path: Path) -> dict[str, Any]:
        """Load a YAML config file by name."""
        path = Path(path)
        if not path.exists():
            logger.warning("Config file not found: %s", path)
            self._configs[name] = {}
            return {}
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        self._configs[name] = data
        self._paths[name] = path
        logger.info("Loaded config '%s' from %s", name, path)
        return data

    def get(self, name: str) -> dict[str, Any]:
        """Get a loaded config by name."""
        return self._configs.get(name, {})

    def reload(self, name: str | None = None) -> None:
        """Reload one or all config files from disk."""
        targets = [name] if name else list(self._paths.keys())
        for n in targets:
            if n in self._paths:
                self.load(n, self._paths[n])
        for cb in self._callbacks:
            cb(targets)

    def on_reload(self, callback: Any) -> None:
        """Register a callback invoked after config reload."""
        self._callbacks.append(callback)

    async def start_watching(self) -> None:
        """Start watching config files for changes (uses watchfiles)."""
        try:
            from watchfiles import awatch
        except ImportError:
            logger.warning("watchfiles not installed, hot-reload disabled")
            return

        paths = list(self._paths.values())
        if not paths:
            return

        watch_dirs = {str(p.parent) for p in paths}

        async def _watch() -> None:
            try:
                async for changes in awatch(*watch_dirs):
                    changed_files = {Path(c[1]) for c in changes}
                    for name, path in self._paths.items():
                        if path.resolve() in {p.resolve() for p in changed_files}:
                            logger.info("Config change detected: %s", name)
                            self.reload(name)
            except asyncio.CancelledError:
                pass

        self._watch_task = asyncio.create_task(_watch())
        logger.info("Config file watcher started")

    async def stop_watching(self) -> None:
        """Stop the file watcher."""
        if self._watch_task:
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass
