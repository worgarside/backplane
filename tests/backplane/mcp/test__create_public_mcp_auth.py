"""Tests for public MCP OAuth auth factory."""

from __future__ import annotations

from typing import TYPE_CHECKING

import anyio
import pytest

from backplane.mcp.auth import create_public_mcp_auth, oauth_tool_meta
from backplane.utils.exceptions import UserError
from backplane.utils.settings import Settings

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

_TEST_OAUTH_CREDENTIAL = "test-oauth-credential"


def test__create_public_mcp_auth__raises_when_oauth_is_not_configured(
    mocker: MockerFixture,
) -> None:
    """The public MCP auth factory refuses to start without OAuth env vars."""
    settings = Settings(obsidian_vault_path=anyio.Path("/tmp/vault"))
    mocker.patch("backplane.mcp.auth.SETTINGS", settings)

    with pytest.raises(UserError, match="Public MCP requires OAuth"):
        create_public_mcp_auth()


def test__create_public_mcp_auth__builds_oidc_proxy_when_oauth_is_configured(
    mocker: MockerFixture,
) -> None:
    """The public MCP auth factory returns an OIDCProxy when OAuth env vars are complete."""
    mock_oidc_proxy = mocker.patch("backplane.mcp.auth.OIDCProxy")
    settings = Settings.model_validate(
        {
            "obsidian_vault_path": "/tmp/vault",
            "mcp_public_base_url": "https://backplane-mcp.example.com",
            "mcp_oidc_config_url": (
                "https://auth.example.com/application/o/backplane-mcp/"
                ".well-known/openid-configuration"
            ),
            "mcp_oidc_client_id": "client-id",
            "mcp_oidc_client_secret": _TEST_OAUTH_CREDENTIAL,
        },
    )
    mocker.patch("backplane.mcp.auth.SETTINGS", settings)

    auth = create_public_mcp_auth()

    assert auth is mock_oidc_proxy.return_value
    mock_oidc_proxy.assert_called_once_with(
        config_url=settings.mcp_oidc_config_url,
        client_id="client-id",
        client_secret=_TEST_OAUTH_CREDENTIAL,
        base_url=settings.mcp_public_base_url,
        require_authorization_consent="external",
        allowed_client_redirect_uris=[
            "https://chatgpt.com/connector/oauth/*",
            "https://chatgpt.com/connector_platform_oauth_redirect",
        ],
        required_scopes=["openid"],
    )


def test__oauth_tool_meta__advertises_openid_oauth2_scheme() -> None:
    """OAuth tool metadata advertises the openid scope to ChatGPT."""
    assert oauth_tool_meta() == {
        "securitySchemes": [{"type": "oauth2", "scopes": ["openid"]}],
    }
