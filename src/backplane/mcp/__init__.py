"""MCP adapter layer for Backplane.

Importing this package registers all domain-specific tools and resources on the
shared ``mcp`` server instance via decorator side-effects. New domains should be
added as sibling modules (e.g. ``frigate.py``, ``home_assistant.py``) and imported
below.
"""

from __future__ import annotations

from . import (
    obsidian,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    tasks,  # noqa: F401  # pyright: ignore[reportUnusedImport]
)
from .server import mcp

__all__ = ["mcp"]
