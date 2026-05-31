"""Public-facing Backplane MCP server entrypoint."""

from __future__ import annotations

import base64
import json
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
    from fastmcp.server.auth import AccessToken as FastMcpAccessToken
    from fastmcp.server.auth import AuthProvider
    from mcp.server.auth.provider import AccessToken as McpAccessToken
    from starlette.requests import Request
    from starlette.responses import Response

_HOST: Final = "0.0.0.0"  # noqa: S104
_PORT: Final = 8001
_VALID_SCOPES: Final = ["openid", "profile", "email"]


def _decode_jwt_part(token: str, part: int) -> dict[str, object] | str | None:
    """Decode a JWT header/payload without validating it.

    Returns:
        Decoded JSON object, decoded string, or ``None`` if the token is not JWT-shaped.
    """
    chunks = token.split(".")
    if len(chunks) <= part:
        return None

    padded = chunks[part] + ("=" * (-len(chunks[part]) % 4))
    try:
        decoded = base64.urlsafe_b64decode(padded.encode("ascii")).decode()
        parsed = cast("object", json.loads(decoded))
    except (ValueError, UnicodeDecodeError) as err:
        return f"<decode failed: {err}>"

    return cast("dict[str, object]", parsed) if isinstance(parsed, dict) else decoded


class DebugOIDCProxy(OIDCProxy):
    """Temporary noisy OAuth debug proxy."""

    @override
    async def verify_token(self, token: str) -> FastMcpAccessToken | None:
        """Log inbound MCP token before FastMCP auth middleware validation.

        Returns:
            Validated access token, or ``None`` if FastMCP rejects it.
        """
        logger.warning("DEBUG verify_token called")
        return await super().verify_token(token)

    @override
    async def load_access_token(self, token: str) -> McpAccessToken | None:
        """Log inbound MCP token details before and after validation.

        Returns:
            Validated access token, or ``None`` if FastMCP rejects it.
        """
        logger.warning("DEBUG MCP bearer token: {}", token)
        logger.warning("DEBUG MCP token header: {}", _decode_jwt_part(token, 0))
        logger.warning("DEBUG MCP token payload: {}", _decode_jwt_part(token, 1))

        result = await super().load_access_token(token)
        if result is None:
            logger.warning("DEBUG MCP token validation result: rejected")
        else:
            logger.warning(
                (
                    "DEBUG MCP token validation result: accepted client_id={} "
                    "scopes={} expires_at={}"
                ),
                result.client_id,
                result.scopes,
                result.expires_at,
            )
        return result


class DebugHttpMiddleware(BaseHTTPMiddleware):
    """Temporary noisy HTTP middleware for OAuth/MCP debugging."""

    @override
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Log MCP request headers before auth middleware handles them.

        Returns:
            Downstream HTTP response.
        """
        if request.url.path == "/mcp":
            authorization = request.headers.get("authorization")
            logger.warning("DEBUG HTTP /mcp method={}", request.method)
            logger.warning("DEBUG HTTP /mcp authorization header={}", authorization)
            logger.warning("DEBUG HTTP /mcp headers={}", dict(request.headers))
            if authorization:
                scheme, _, token = authorization.partition(" ")
                logger.warning("DEBUG HTTP /mcp auth scheme={}", scheme)
                logger.warning("DEBUG HTTP /mcp auth token={}", token)
                logger.warning(
                    "DEBUG HTTP /mcp auth token header={}",
                    _decode_jwt_part(token, 0),
                )
                logger.warning(
                    "DEBUG HTTP /mcp auth token payload={}",
                    _decode_jwt_part(token, 1),
                )

        response = await call_next(request)
        if request.url.path == "/mcp":
            logger.warning("DEBUG HTTP /mcp response status={}", response.status_code)
        return response


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
    logger.warning(
        (
            "DEBUG creating public MCP auth provider class={} base_url={} issuer={} "
            "oidc_config_url={} scopes={}"
        ),
        DebugOIDCProxy.__name__,
        settings.mcp_public_base_url,
        settings.mcp_oauth_issuer,
        oidc_config_url,
        _VALID_SCOPES,
    )

    return DebugOIDCProxy(
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
    mcp = create_mcp_server(auth=create_auth_provider())
    uvloop.run(
        mcp.run_async(
            transport="http",
            host=_HOST,
            port=_PORT,
            middleware=[Middleware(DebugHttpMiddleware)],
        ),
    )
