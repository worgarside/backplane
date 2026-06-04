"""Tests for browser CORS on the Streamable HTTP /mcp endpoint."""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route
from starlette.testclient import TestClient

from backplane.mcp.auth import browser_mcp_app_cors


async def _mcp_stub(_: Request) -> Response:
    return Response(status_code=204)


def test__browser_mcp_app_cors__allows_mcp_preflight_from_inspector() -> None:
    """MCP Inspector direct connections preflight /mcp with Authorization and MCP headers."""
    app = browser_mcp_app_cors(
        Starlette(
            routes=[
                Route("/mcp", endpoint=_mcp_stub, methods=["POST", "DELETE"]),
            ],
        ),
    )
    client = TestClient(app)

    response = client.options(
        "/mcp",
        headers={
            "Origin": "http://localhost:6274",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": (
                "authorization, content-type, mcp-protocol-version"
            ),
        },
    )

    assert response.status_code == 200
    allow_headers = response.headers.get("access-control-allow-headers", "").lower()
    assert "authorization" in allow_headers
    assert "mcp-protocol-version" in allow_headers
    assert "mcp-session-id" in allow_headers


def test__browser_mcp_app_cors__exposes_mcp_session_id_on_responses() -> None:
    """Inspector reads mcp-session-id from Access-Control-Expose-Headers on POST responses."""
    app = browser_mcp_app_cors(
        Starlette(
            routes=[
                Route("/mcp", endpoint=_mcp_stub, methods=["POST"]),
            ],
        ),
    )
    client = TestClient(app)

    response = client.post("/mcp", headers={"Origin": "http://localhost:6274"})

    assert response.status_code == 204
    expose_headers = response.headers.get("access-control-expose-headers", "").lower()
    assert "mcp-session-id" in expose_headers
