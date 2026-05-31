"""Tests for public MCP OAuth settings."""

from __future__ import annotations

import anyio
import pytest

from backplane.utils.settings import Settings

_TEST_OAUTH_CREDENTIAL = "test-oauth-credential"


def test__mcp_oauth_configured__returns_false_when_oauth_env_vars_are_missing() -> None:
    """OAuth is considered unconfigured when any required MCP OAuth env var is absent."""
    settings = Settings(
        obsidian_vault_path=anyio.Path("/tmp/vault"),
    )

    assert settings.mcp_oauth_configured is False


def test__mcp_oauth_configured__returns_true_when_all_oauth_env_vars_are_present() -> (
    None
):
    """OAuth is configured only when every required MCP OAuth env var is set."""
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

    assert settings.mcp_oauth_configured is True


@pytest.mark.parametrize(
    ("field_name", "value", "expected"),
    [
        (
            "mcp_public_base_url",
            "https://backplane-mcp.example.com",
            "https://backplane-mcp.example.com/",
        ),
        (
            "mcp_oidc_config_url",
            "https://auth.example.com/application/o/x/.well-known/openid-configuration",
            "https://auth.example.com/application/o/x/.well-known/openid-configuration",
        ),
    ],
)
def test__settings__parse_mcp_url_fields(
    field_name: str,
    value: str,
    expected: str,
) -> None:
    """MCP OAuth URL settings accept string env values."""
    settings = Settings.model_validate(
        {
            "obsidian_vault_path": "/tmp/vault",
            field_name: value,
        },
    )

    parsed = getattr(settings, field_name)
    assert parsed is not None
    assert str(parsed) == expected
