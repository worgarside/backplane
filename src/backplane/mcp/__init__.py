"""MCP adapter layer for Backplane.

Server entrypoints create a FastMCP instance with ``create_mcp_server`` and register
all domain-specific tools/resources onto that instance. New domains should expose a
``register_*`` function and be called from ``server.create_mcp_server``.
"""

from __future__ import annotations

from .server import create_mcp_server

__all__ = ["create_mcp_server"]
