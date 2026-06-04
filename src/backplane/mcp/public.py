"""Public-facing Backplane MCP server entrypoint."""

from __future__ import annotations

from typing import Final

import uvicorn
import uvloop
from loguru import logger

from backplane import __version__
from backplane.mcp import create_mcp_server
from backplane.mcp.auth import create_public_mcp_auth

_HOST: Final = "0.0.0.0"  # noqa: S104
_PORT: Final = 8001

if __name__ == "__main__":
    auth = create_public_mcp_auth()
    logger.info(
        "Starting public Backplane MCP server v{} on {}:{} with OAuth",
        __version__,
        _HOST,
        _PORT,
    )
    mcp = create_mcp_server(auth=auth, require_oauth=True)
    # Session-based Streamable HTTP (not stateless): ChatGPT probes GET /mcp and
    # expects JSON responses; stateless mode returns 405 on GET.
    app = mcp.http_app(
        transport="http",
        stateless_http=False,
        json_response=True,
    )

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
