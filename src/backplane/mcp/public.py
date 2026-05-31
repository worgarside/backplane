"""Public-facing Backplane MCP server entrypoint."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Final

import uvloop
from fastmcp.server.auth import OIDCProxy
from loguru import logger
from pydantic import Field
from pydantic_settings import BaseSettings

from backplane import __version__
from backplane.mcp import create_mcp_server

if TYPE_CHECKING:
    from fastmcp.server.auth import AuthProvider

_HOST: Final = "0.0.0.0"  # noqa: S104
_PORT: Final = 8001
_VALID_SCOPES: Final = ["openid", "profile", "email"]


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
        str | None,
        Field(
            default=None,
            description=(
                "Optional expected token audience for Backplane MCP. Set this only "
                "when Authentik includes a stable aud claim in access tokens."
            ),
        ),
    ]


def create_auth_provider() -> AuthProvider:
    """Create the Authentik-backed OAuth provider for the public MCP server.

    Returns:
        Configured FastMCP auth provider.
    """
    settings = PublicMcpOAuthSettings()  # pyright: ignore[reportCallIssue]
    oidc_config_url = (
        f"{settings.mcp_oauth_issuer.rstrip('/')}/.well-known/openid-configuration"
    )
    return OIDCProxy(
        config_url=oidc_config_url,
        client_id=settings.mcp_oauth_client_id,
        client_secret=settings.mcp_oauth_client_secret,
        audience=settings.mcp_oauth_audience,
        base_url=settings.mcp_public_base_url,
        required_scopes=_VALID_SCOPES,
        verify_id_token=True,
    )


if __name__ == "__main__":
    logger.info(
        "Starting public Backplane MCP server v{} on {}:{}",
        __version__,
        _HOST,
        _PORT,
    )
    auth_provider = create_auth_provider()
    mcp = create_mcp_server()
    mcp._additional_http_routes.extend(  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
        auth_provider.get_routes(mcp_path="/mcp"),
    )
    uvloop.run(mcp.run_async(transport="http", host=_HOST, port=_PORT))
