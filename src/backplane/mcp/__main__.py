"""Entrypoint for running the Backplane MCP server."""

from __future__ import annotations

from typing import Final

import uvloop
from loguru import logger

from backplane import __version__
from backplane.mcp import create_mcp_server

_HOST: Final = "0.0.0.0"  # noqa: S104
_PORT: Final = 8000

if __name__ == "__main__":
    logger.info("Starting Backplane MCP server v{} on {}:{}", __version__, _HOST, _PORT)
    mcp = create_mcp_server(notify_home_assistant=True)
    uvloop.run(mcp.run_async(transport="sse", host=_HOST, port=_PORT))
