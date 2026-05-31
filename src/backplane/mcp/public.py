"""Public-facing Backplane MCP server entrypoint."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Annotated, Final, cast, override
from urllib.parse import parse_qs

import uvloop
from fastmcp.server.auth import OIDCProxy
from loguru import logger
from pydantic import Field
from pydantic_settings import BaseSettings
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response as StarletteResponse

from backplane import __version__
from backplane.mcp import create_mcp_server

if TYPE_CHECKING:
    from fastmcp.server.auth import AuthProvider
    from starlette.responses import Response
    from starlette.types import Message

_HOST: Final = "0.0.0.0"  # noqa: S104
_PORT: Final = 8001
_VALID_SCOPES: Final = ["openid", "profile", "email"]
_MCP_ACCEPT_HEADER: Final = b"application/json, text/event-stream"
_REDACTED_HEADER_VALUE: Final = "<redacted>"
_SENSITIVE_HEADER_NAMES: Final = frozenset(
    {
        "authorization",
        "cookie",
        "proxy-authorization",
        "x-api-key",
    },
)
_SENSITIVE_BODY_KEYS: Final = frozenset(
    {
        "access_token",
        "client_secret",
        "code",
        "id_token",
        "password",
        "refresh_token",
        "token",
    },
)
_DEBUG_BODY_MAX_BYTES: Final = 2048


def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
    """Return request headers with sensitive values redacted."""
    return {
        key: _REDACTED_HEADER_VALUE if key.lower() in _SENSITIVE_HEADER_NAMES else value
        for key, value in headers.items()
    }


def _redact_body_preview(body: bytes, content_type: str | None) -> str:
    """Return a log-safe preview of a request body."""
    if not body:
        return "<empty>"

    if content_type and "application/json" in content_type:
        try:
            parsed = cast("object", json.loads(body))
        except json.JSONDecodeError:
            return repr(body[:_DEBUG_BODY_MAX_BYTES])
        if isinstance(parsed, dict):
            payload = cast("dict[str, object]", parsed)
            redacted = {
                key: _REDACTED_HEADER_VALUE
                if key.lower() in _SENSITIVE_BODY_KEYS
                else value
                for key, value in payload.items()
            }
            return json.dumps(redacted)[:_DEBUG_BODY_MAX_BYTES]
        return json.dumps(parsed)[:_DEBUG_BODY_MAX_BYTES]

    if content_type and "application/x-www-form-urlencoded" in content_type:
        form = parse_qs(body.decode(errors="replace"))
        redacted = {
            key: [_REDACTED_HEADER_VALUE]
            if key.lower() in _SENSITIVE_BODY_KEYS
            else values
            for key, values in form.items()
        }
        return repr(redacted)[:_DEBUG_BODY_MAX_BYTES]

    return repr(body[:_DEBUG_BODY_MAX_BYTES])


def _log_mcp_post_body(body: bytes) -> None:
    """Log a safe preview of an inbound ChatGPT MCP POST body."""
    if not body:
        logger.warning("ChatGPT /mcp body is empty")
        return

    try:
        parsed = cast("object", json.loads(body))
    except json.JSONDecodeError:
        logger.warning(
            "ChatGPT /mcp body is not JSON (len={} preview={!r})",
            len(body),
            body[:500],
        )
        return

    if not isinstance(parsed, dict):
        logger.warning(
            "ChatGPT /mcp JSON is not an object: type={}",
            type(parsed).__name__,
        )
        return

    payload = cast("dict[str, object]", parsed)
    params = payload.get("params")
    protocol_version = (
        cast("dict[str, object]", params).get("protocolVersion")
        if isinstance(params, dict)
        else None
    )
    logger.warning(
        "ChatGPT /mcp JSON method={} id={} protocolVersion={}",
        payload.get("method"),
        payload.get("id"),
        protocol_version,
    )


def _request_with_body(request: Request, body: bytes) -> Request:
    """Return a new request whose body can be read again downstream."""

    async def receive() -> Message:  # noqa: RUF029
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(request.scope, receive)


def _normalize_chatgpt_mcp_headers(
    headers: list[tuple[bytes, bytes]],
) -> list[tuple[bytes, bytes]]:
    """Rewrite ChatGPT's octet-stream MCP headers to MCP-compatible values.

    Returns:
        Header list with MCP-compatible content-type and accept values.
    """
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

    return rewritten_headers


class DebugHttpLoggingMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request while MCP_PUBLIC_DEBUG_HTTP is enabled."""

    @override
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Log inbound request metadata and response status.

        Returns:
            Downstream HTTP response.
        """
        body = b""
        if request.method in {"POST", "PUT", "PATCH"}:
            body = await request.body()
            request = _request_with_body(request, body)

        logger.warning(
            "DEBUG HTTP {} {} query={} headers={}",
            request.method,
            request.url.path,
            request.url.query or "<none>",
            _redact_headers(dict(request.headers)),
        )
        if body:
            logger.warning(
                "DEBUG HTTP {} {} body_preview={}",
                request.method,
                request.url.path,
                _redact_body_preview(body, request.headers.get("content-type")),
            )

        response = await call_next(request)
        logger.warning(
            "DEBUG HTTP {} {} -> {}",
            request.method,
            request.url.path,
            response.status_code,
        )
        return response


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
        if request.url.path != "/mcp" or request.method != "POST":
            return await call_next(request)

        body = await request.body()
        content_type = request.headers.get("content-type")
        logger.warning(
            (
                "ChatGPT /mcp request content-type={} accept={} "
                "mcp-session-id={} mcp-protocol-version={} authorization={} body_len={}"
            ),
            content_type,
            request.headers.get("accept"),
            request.headers.get("mcp-session-id"),
            request.headers.get("mcp-protocol-version"),
            "present" if request.headers.get("authorization") else "missing",
            len(body),
        )
        _log_mcp_post_body(body)

        if not body and not request.headers.get("authorization"):
            logger.warning(
                "ChatGPT /mcp allowing empty unauthenticated discovery probe",
            )
            return StarletteResponse(status_code=200)

        headers = cast("list[tuple[bytes, bytes]]", request.scope["headers"])
        if content_type == "application/octet-stream":
            logger.warning("Rewriting ChatGPT /mcp content-type and accept headers")
            headers = _normalize_chatgpt_mcp_headers(headers)

        request = _request_with_body(request, body)
        request.scope["headers"] = headers
        response = await call_next(request)
        logger.warning("ChatGPT /mcp response status={}", response.status_code)
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
    mcp_public_debug_http: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "Log all public MCP HTTP requests with redacted secrets. "
                "Disable before merging."
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
    settings = PublicMcpOAuthSettings()  # pyright: ignore[reportCallIssue]
    auth_provider = create_auth_provider()
    mcp = create_mcp_server(auth=auth_provider)
    middleware: list[Middleware] = [Middleware(ChatGptMcpCompatibilityMiddleware)]
    if settings.mcp_public_debug_http:
        logger.warning("MCP_PUBLIC_DEBUG_HTTP enabled: logging all HTTP requests")
        middleware.insert(0, Middleware(DebugHttpLoggingMiddleware))
    uvloop.run(
        mcp.run_async(
            transport="http",
            host=_HOST,
            port=_PORT,
            stateless_http=True,
            middleware=middleware,
        ),
    )
