"""Public-facing Backplane MCP server entrypoint."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import uvicorn
import uvloop
from loguru import logger

from backplane import __version__
from backplane.mcp import create_mcp_server
from backplane.mcp.auth import create_public_mcp_auth

if TYPE_CHECKING:
    from fastmcp.server.http import StarletteWithLifespan

_HOST: Final = "0.0.0.0"  # noqa: S104
_PORT: Final = 8001


def create_public_mcp_app() -> StarletteWithLifespan:
    """Build the authenticated public MCP HTTP ASGI app.

    Returns:
        Streamable HTTP ASGI app for the ChatGPT-facing MCP server.
    """
    auth = create_public_mcp_auth()
    mcp = create_mcp_server(auth=auth, require_oauth=True)
    return mcp.http_app(transport="http")


def main() -> None:
    """Run the public MCP server until interrupted."""
    logger.info(
        "Starting public Backplane MCP server v{} on {}:{} with OAuth",
        __version__,
        _HOST,
        _PORT,
    )
    app = create_public_mcp_app()

    uvloop.run(
        uvicorn.Server(
            uvicorn.Config(
                app,
                host=_HOST,
                port=_PORT,
                log_level="info",
            ),
        ).serve(),
    )


if __name__ == "__main__":
    main()
