"""Public-facing Backplane MCP server entrypoint."""

from __future__ import annotations

from typing import Any, Final

import uvicorn
import uvloop
from loguru import logger

from backplane import __version__
from backplane.mcp import create_mcp_server
from backplane.mcp.auth import browser_mcp_app_cors, create_public_mcp_auth
from backplane.mcp.debug_http import FullRequestLoggingASGIApp
from backplane.utils.settings import SETTINGS

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
    inner_app = mcp.http_app(
        transport="http",
        stateless_http=True,
    )
    app: Any = browser_mcp_app_cors(inner_app)
    if SETTINGS.mcp_public_debug_http:
        logger.warning(
            "MCP_PUBLIC_DEBUG_HTTP enabled — logging full HTTP headers and bodies"
        )
        app = FullRequestLoggingASGIApp(app)

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
