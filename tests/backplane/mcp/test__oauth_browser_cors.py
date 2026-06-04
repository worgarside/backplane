"""Tests for browser OAuth CORS used by MCP Inspector."""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

from backplane.mcp.auth import oauth_browser_cors_middleware


async def _token_stub(_: Request) -> Response:
    return JSONResponse({"ok": True})


def test__oauth_browser_cors__allows_content_type_on_token_preflight() -> None:
    """Token preflight from MCP Inspector may request Content-Type for form POSTs."""
    app = Starlette(
        routes=[
            Route(
                "/token",
                endpoint=oauth_browser_cors_middleware(
                    _token_stub,
                    ["POST", "OPTIONS"],
                ),
                methods=["POST", "OPTIONS"],
            ),
        ],
    )
    client = TestClient(app)

    response = client.options(
        "/token",
        headers={
            "Origin": "http://localhost:6274",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    allow_headers = response.headers.get("access-control-allow-headers", "").lower()
    assert "content-type" in allow_headers
