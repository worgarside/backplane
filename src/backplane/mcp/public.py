"""Public-facing Backplane MCP server entrypoint."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Final, cast, override

import uvloop
from fastmcp.server.auth import OIDCProxy
from loguru import logger
from pydantic import Field
from pydantic_settings import BaseSettings
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from backplane import __version__
from backplane.mcp import create_mcp_server

if TYPE_CHECKING:
    from fastmcp.server.auth import AuthProvider
    from starlette.requests import Request
    from starlette.responses import Response

_HOST: Final = "0.0.0.0"  # noqa: S104
_PORT: Final = 8001
_VALID_SCOPES: Final = ["openid", "profile", "email"]
_MCP_ACCEPT_HEADER: Final = b"application/json, text/event-stream"


class ChatGptMcpCompatibilityMiddleware(BaseHTTPMiddleware):
    """Normalize ChatGPT's MCP request headers before FastMCP parses them."""

    @override
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Rewrite ChatGPT's octet-stream MCP posts as JSON requests.

        Returns:
            Downstream HTTP response.
        """
        if request.url.path == "/mcp" and request.method == "POST":
            headers = cast("list[tuple[bytes, bytes]]", request.scope["headers"])
            content_type = request.headers.get("content-type")
            accept = request.headers.get("accept")
            logger.warning(
                "ChatGPT /mcp request content-type={} accept={}",
                content_type,
                accept,
            )
            if content_type != "application/octet-stream":
                return await call_next(request)

            logger.warning(
                "Rewriting ChatGPT /mcp content-type and accept headers",
            )
            rewritten_headers: list[tuple[bytes, bytes]] = []
            has_accept = False
            for name, value in headers:
                if name == b"content-type":
                    rewritten_headers.append((name, b"application/json"))
                elif name == b"accept":
                    has_accept = True
                    rewritten_headers.append((name, _MCP_ACCEPT_HEADER))
                else:
                    rewritten_headers.append((name, value))

            if not has_accept:
                rewritten_headers.append((b"accept", _MCP_ACCEPT_HEADER))

            request.scope["headers"] = rewritten_headers

        return await call_next(request)


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
    uvloop.run(
        mcp.run_async(
            transport="http",
            host=_HOST,
            port=_PORT,
            middleware=[Middleware(ChatGptMcpCompatibilityMiddleware)],
        ),
    )
