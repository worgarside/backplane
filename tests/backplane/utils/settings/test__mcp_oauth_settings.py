"""Tests for public MCP OAuth settings."""

from __future__ import annotations

import anyio
import pytest
from pytest import MonkeyPatch

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


def test__settings__parse_mcp_extra_allowed_client_redirect_uris() -> None:
    """Extra MCP redirect URI patterns accept comma-separated env values."""
    raw_value = (
        "http://127.0.0.1:6274/oauth/callback/debug,http://localhost:*/cb"
    )
    expected = [
        "http://127.0.0.1:6274/oauth/callback/debug",
        "http://localhost:*/cb",
    ]
    settings = Settings.model_validate(
        {
            "obsidian_vault_path": "/tmp/vault",
            "mcp_extra_allowed_client_redirect_uris": raw_value,
        },
    )

    assert settings.mcp_extra_allowed_client_redirect_uris == expected


def test__settings__loads_comma_separated_redirect_uris_from_env(
    monkeypatch: MonkeyPatch,
) -> None:
    """Comma-separated redirect URI env values are not JSON-decoded by pydantic-settings."""
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", "/tmp/vault")
    monkeypatch.setenv(
        "MCP_EXTRA_ALLOWED_CLIENT_REDIRECT_URIS",
        "http://127.0.0.1:*/oauth/callback/*,http://localhost:*/cb",
    )

    settings = Settings()

    assert settings.mcp_extra_allowed_client_redirect_uris == [
        "http://127.0.0.1:*/oauth/callback/*",
        "http://localhost:*/cb",
    ]


def test__settings__allowed_client_redirect_uri_patterns_merges_defaults_and_extras() -> (
    None
):
    """Allowed redirect patterns include ChatGPT defaults plus configured extras."""
    settings = Settings.model_validate(
        {
            "obsidian_vault_path": "/tmp/vault",
            "mcp_extra_allowed_client_redirect_uris": (
                "http://127.0.0.1:*/oauth/callback/*"
            ),
        },
    )

    assert settings.allowed_client_redirect_uri_patterns == [
        "https://chatgpt.com/connector/oauth/*",
        "https://chatgpt.com/connector_platform_oauth_redirect",
        "http://127.0.0.1:*/oauth/callback/*",
    ]
