"""Integration checks for public MCP OAuth HTTP endpoints."""

from __future__ import annotations

import httpx
import pytest
from fastmcp.server.auth import RemoteAuthProvider
from fastmcp.server.auth.providers.jwt import JWTVerifier
from pydantic import AnyHttpUrl

from backplane.mcp import create_mcp_server


@pytest.fixture
def mock_auth_provider() -> RemoteAuthProvider:
    """Provide a minimal auth provider that exposes OAuth discovery routes."""
    token_verifier = JWTVerifier(
        jwks_uri="https://auth.example.com/application/o/backplane-mcp/jwks/",
        issuer="https://auth.example.com/application/o/backplane-mcp/",
        audience="https://backplane-mcp.example.com/mcp",
    )
    return RemoteAuthProvider(
        token_verifier=token_verifier,
        authorization_servers=[
            AnyHttpUrl("https://auth.example.com/application/o/backplane-mcp/"),
        ],
        base_url="https://backplane-mcp.example.com",
    )


async def test__public_mcp_oauth__protected_resource_metadata_is_exposed(
    mock_auth_provider: RemoteAuthProvider,
) -> None:
    """The public MCP HTTP app exposes OAuth protected resource metadata."""
    mcp = create_mcp_server(auth=mock_auth_provider, require_oauth=True)
    app = mcp.http_app(stateless_http=True)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://backplane-mcp.example.com",
    ) as client:
        response = await client.get("/.well-known/oauth-protected-resource/mcp")

    assert response.status_code == httpx.codes.OK
    payload = response.json()
    assert "resource" in payload
    assert payload["authorization_servers"] == [
        "https://auth.example.com/application/o/backplane-mcp/",
    ]


async def test__public_mcp_oauth__unauthenticated_mcp_request_returns_401(
    mock_auth_provider: RemoteAuthProvider,
) -> None:
    """Unauthenticated MCP requests receive a WWW-Authenticate challenge."""
    mcp = create_mcp_server(auth=mock_auth_provider, require_oauth=True)
    app = mcp.http_app(stateless_http=True)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://backplane-mcp.example.com",
    ) as client:
        response = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        )

    assert response.status_code == httpx.codes.UNAUTHORIZED
    assert "WWW-Authenticate" in response.headers
    assert "oauth-protected-resource" in response.headers["WWW-Authenticate"]

