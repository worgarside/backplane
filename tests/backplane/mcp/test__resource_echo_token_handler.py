"""Tests for RFC 8707 resource echo token handler body replay."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

from backplane.mcp.auth import (
    _inject_client_id_from_authorization_code,
    _request_with_replayed_body,
)


async def _read_client_id_twice(request: Request) -> Response:
    """Simulate resource echo then client auth both calling ``request.form()``."""
    body = await request.body()
    replayed = _request_with_replayed_body(request, body)
    first = (await replayed.form()).get("client_id")
    second = (await replayed.form()).get("client_id")
    return JSONResponse({"first": first, "second": second})


@dataclass
class _SampleClientCode:
    client_id: str


class _SampleCodeStore:
    def __init__(self, codes: dict[str, _SampleClientCode]) -> None:
        self._codes = codes

    async def get(self, key: str) -> _SampleClientCode | None:
        return self._codes.get(key)


class _SampleOAuthProvider:
    def __init__(self, codes: dict[str, _SampleClientCode]) -> None:
        self._code_store = _SampleCodeStore(codes)


@pytest.mark.parametrize(
    "body",
    [
        (
            "grant_type=authorization_code&code=Agbrz50Ym5PKlrOmu78ASQFEJBNhVjp_oEbU4oKNZhw"
            "&code_verifier=verifier&redirect_uri=http%3A%2F%2F127.0.0.1%3A6274%2Foauth"
            "%2Fcallback%2Fdebug&resource=https%3A%2F%2Fbackplane-mcp.example.com%2Fmcp"
        ),
    ],
)
async def test__inject_client_id_from_authorization_code__fills_missing_client_id(
    body: str,
) -> None:
    """MCP Inspector-style token requests without client_id are completed from the code store."""
    parsed = parse_qs(body, keep_blank_values=True)
    provider = _SampleOAuthProvider(
        {
            "Agbrz50Ym5PKlrOmu78ASQFEJBNhVjp_oEbU4oKNZhw": _SampleClientCode(
                client_id="inspector-dcr-client",
            ),
        },
    )

    enriched = await _inject_client_id_from_authorization_code(provider, parsed)

    assert enriched.get("client_id") == ["inspector-dcr-client"]


def test__request_with_replayed_body__preserves_form_fields_for_token_handler() -> None:
    """Replayed bodies still expose client_id when form() is read after body()."""
    app = Starlette(
        routes=[
            Route(
                "/token",
                endpoint=_read_client_id_twice,
                methods=["POST"],
            ),
        ],
    )
    client = TestClient(app)

    response = client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "client_id": "inspector-client",
            "code": "abc",
            "code_verifier": "verifier",
            "resource": "https://backplane-mcp.example.com/mcp",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "first": "inspector-client",
        "second": "inspector-client",
    }
