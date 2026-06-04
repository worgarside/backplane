"""Temporary public MCP server with full HTTP request/response logging.

Run instead of ``backplane.mcp.public`` while debugging ChatGPT OAuth:

    python -m backplane.mcp.public_debug

Logs every header and body (no redaction) for all routes: ``/mcp``, ``/token``,
``/authorize``, ``/.well-known/*``, etc.
"""

from __future__ import annotations

from typing import Final

import uvicorn
import uvloop
from loguru import logger

from backplane import __version__
from backplane.mcp import create_mcp_server
from backplane.mcp.auth import browser_mcp_app_cors, create_public_mcp_auth
from backplane.mcp.debug_http import FullRequestLoggingASGIApp

_HOST: Final = "0.0.0.0"  # noqa: S104
_PORT: Final = 8001

if __name__ == "__main__":
    auth = create_public_mcp_auth()
    logger.warning(
        "Starting MCP HTTP DEBUG server v{} on {}:{} — full headers/bodies logged",
        __version__,
        _HOST,
        _PORT,
    )
    mcp = create_mcp_server(auth=auth, require_oauth=True)
    inner_app = mcp.http_app(
        transport="http",
        stateless_http=False,
        json_response=True,
    )
    app = FullRequestLoggingASGIApp(browser_mcp_app_cors(inner_app))

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
