"""Entrypoint for running the Backplane MCP server."""

from __future__ import annotations

from typing import Final

from loguru import logger

from backplane import __version__
from backplane.mcp import mcp

_HOST: Final = "0.0.0.0"  # noqa: S104
_PORT: Final = 8000

if __name__ == "__main__":
    logger.info("Starting Backplane MCP server v{} on {}:{}", __version__, _HOST, _PORT)
    mcp.run(transport="sse", host=_HOST, port=_PORT)
