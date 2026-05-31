"""Public-facing Backplane MCP server entrypoint."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Final

import uvloop
from fastmcp.server.auth import OAuthProxy
from fastmcp.server.auth.providers.jwt import JWTVerifier
from loguru import logger
from pydantic import Field
from pydantic_settings import BaseSettings

from backplane import __version__
from backplane.mcp import create_mcp_server

if TYPE_CHECKING:
    from fastmcp.server.auth import AuthProvider

_HOST: Final = "0.0.0.0"  # noqa: S104
_PORT: Final = 8001


class PublicMcpOAuthSettings(BaseSettings):
    """Required OAuth/OIDC settings for the public MCP server."""

    mcp_public_base_url: Annotated[
        str,
        Field(description=("Public HTTPS base URL for the public-facing MCP server")),
    ]
    mcp_oauth_issuer: Annotated[
        str,
        Field(description="Authentik OIDC issuer URL for the Backplane MCP provider."),
    ]
    mcp_oauth_authorization_endpoint: Annotated[
        str,
        Field(description="Authentik OAuth authorization endpoint for Backplane MCP."),
    ]
    mcp_oauth_token_endpoint: Annotated[
        str,
        Field(description="Authentik OAuth token endpoint for Backplane MCP."),
    ]
    mcp_oauth_jwks_uri: Annotated[
        str,
        Field(description="Authentik JWKS URI for validating Backplane MCP tokens."),
    ]
    mcp_oauth_client_id: Annotated[
        str,
        Field(description="Authentik OAuth client ID for Backplane MCP."),
    ]
    mcp_oauth_client_secret: Annotated[
        str,
        Field(description="Authentik OAuth client secret for Backplane MCP."),
    ]
    mcp_oauth_audience: Annotated[
        str,
        Field(
            description=(
                "Expected token audience for Backplane MCP. For Authentik this is "
                "usually the provider client ID unless configured otherwise."
            ),
        ),
    ]


def create_auth_provider() -> AuthProvider:
    """Create the Authentik-backed OAuth provider for the public MCP server.

    Returns:
        Configured FastMCP auth provider.
    """
    settings = PublicMcpOAuthSettings()  # pyright: ignore[reportCallIssue]

    token_verifier = JWTVerifier(
        jwks_uri=settings.mcp_oauth_jwks_uri,
        issuer=settings.mcp_oauth_issuer,
        audience=settings.mcp_oauth_audience,
    )
    return OAuthProxy(
        upstream_authorization_endpoint=settings.mcp_oauth_authorization_endpoint,
        upstream_token_endpoint=settings.mcp_oauth_token_endpoint,
        upstream_client_id=settings.mcp_oauth_client_id,
        upstream_client_secret=settings.mcp_oauth_client_secret,
        token_verifier=token_verifier,
        base_url=settings.mcp_public_base_url,
    )


if __name__ == "__main__":
    logger.info(
        "Starting public Backplane MCP server v{} on {}:{}",
        __version__,
        _HOST,
        _PORT,
    )
    mcp = create_mcp_server(auth=create_auth_provider())
    uvloop.run(mcp.run_async(transport="http", host=_HOST, port=_PORT))
