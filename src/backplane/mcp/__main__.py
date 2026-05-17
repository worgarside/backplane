"""Entrypoint for running the Backplane MCP server."""

from __future__ import annotations

from typing import Final

import uvloop

from backplane.mcp import mcp

_HOST: Final = "0.0.0.0"  # noqa: S104
_PORT: Final = 8000

if __name__ == "__main__":
    uvloop.run(mcp.run_async(transport="sse", host=_HOST, port=_PORT))
