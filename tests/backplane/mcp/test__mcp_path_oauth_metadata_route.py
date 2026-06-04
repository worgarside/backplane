"""Tests for ChatGPT-facing OAuth authorization-server metadata paths."""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from backplane.mcp.auth import _add_mcp_path_oauth_authorization_server_metadata_route


async def _metadata_stub(_: Request) -> Response:
    return Response(status_code=204)


def test__add_mcp_path_oauth_authorization_server_metadata_route__adds_mcp_suffix() -> (
    None
):
    """Resource-specific well-known path is registered for /mcp ChatGPT discovery."""
    routes = [
        Route(
            "/.well-known/oauth-authorization-server",
            endpoint=_metadata_stub,
            methods=["GET"],
        ),
    ]

    extended = _add_mcp_path_oauth_authorization_server_metadata_route(
        routes,
        "/mcp",
    )

    paths = [route.path for route in extended]
    assert "/.well-known/oauth-authorization-server/mcp" in paths
