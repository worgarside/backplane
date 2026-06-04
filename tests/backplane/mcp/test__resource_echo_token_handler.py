"""Tests for RFC 8707 resource echo token handler body replay."""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

from backplane.mcp.auth import _request_with_replayed_body


async def _read_client_id_twice(request: Request) -> Response:
    """Simulate resource echo then client auth both calling ``request.form()``."""
    body = await request.body()
    replayed = _request_with_replayed_body(request, body)
    first = (await replayed.form()).get("client_id")
    second = (await replayed.form()).get("client_id")
    return JSONResponse({"first": first, "second": second})


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
