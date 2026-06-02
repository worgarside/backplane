"""Temporary full HTTP request/response logging for MCP OAuth debugging.

Wrap a Starlette/FastMCP ASGI app with ``FullRequestLoggingASGIApp`` to log
every header and body with no redaction. Remove or stop using this once OAuth
is working.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

_MCP_HTTP_DEBUG_PREFIX = "MCP_HTTP_DEBUG"


def _decode_header_pairs(headers: list[tuple[bytes, bytes]]) -> dict[str, str]:
    return {name.decode("latin-1"): value.decode("latin-1") for name, value in headers}


def _format_body(raw: bytes) -> str:
    if not raw:
        return "<empty>"
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return repr(raw)


class FullRequestLoggingASGIApp:
    """Outermost ASGI wrapper that logs full HTTP exchanges."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "?")
        path = scope.get("path", "?")
        query = scope.get("query_string", b"").decode("latin-1")
        client = scope.get("client")
        request_headers = _decode_header_pairs(scope.get("headers", []))

        request_body = b""

        async def logging_receive() -> dict[str, Any]:
            nonlocal request_body
            message = await receive()
            if message["type"] == "http.request":
                request_body += message.get("body", b"")
            return message

        response_status: int | None = None
        response_headers: dict[str, str] = {}
        response_body = b""

        async def logging_send(message: dict[str, Any]) -> None:
            nonlocal response_status, response_body
            if message["type"] == "http.response.start":
                response_status = message.get("status")
                response_headers = _decode_header_pairs(message.get("headers", []))
            elif message["type"] == "http.response.body":
                response_body += message.get("body", b"")
            await send(message)

        try:
            await self.app(scope, logging_receive, logging_send)
        except Exception:
            logger.exception(
                "{} unhandled exception during {} {}",
                _MCP_HTTP_DEBUG_PREFIX,
                method,
                path,
            )
            raise
        finally:
            logger.warning(
                "\n".join(
                    [
                        f"=== {_MCP_HTTP_DEBUG_PREFIX} EXCHANGE ===",
                        f"client: {client!r}",
                        f"REQUEST: {method} {path}",
                        f"query: {query or '<empty>'}",
                        "request headers:",
                        *(
                            f"  {name}: {value}"
                            for name, value in request_headers.items()
                        ),
                        f"request body ({len(request_body)} bytes):",
                        _format_body(request_body),
                        f"RESPONSE: {response_status}",
                        "response headers:",
                        *(
                            f"  {name}: {value}"
                            for name, value in response_headers.items()
                        ),
                        f"response body ({len(response_body)} bytes):",
                        _format_body(response_body),
                        f"=== END {_MCP_HTTP_DEBUG_PREFIX} ===",
                    ],
                ),
            )
