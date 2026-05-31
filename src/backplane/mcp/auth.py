"""OAuth authentication for the public Backplane MCP server."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastmcp.server.auth import require_scopes
from fastmcp.server.auth.oidc_proxy import OIDCProxy
from loguru import logger

from backplane.utils.settings import SETTINGS

if TYPE_CHECKING:
    from fastmcp.server.auth import AuthProvider

_CHATGPT_REDIRECT_URIS: tuple[str, ...] = (
    "https://chatgpt.com/connector/oauth/*",
    "https://chatgpt.com/connector_platform_oauth_redirect",
)


def oauth_tool_meta() -> dict[str, object]:
    """Return MCP tool metadata that advertises OAuth to ChatGPT."""
    return {
        "securitySchemes": [{"type": "oauth2", "scopes": ["openid"]}],
    }


def oauth_tool_registration_kwargs() -> dict[str, object]:
    """Return FastMCP registration kwargs for OAuth-protected tools and resources."""
    return {
        "auth": require_scopes("openid"),
        "meta": oauth_tool_meta(),
    }


def create_public_mcp_auth() -> AuthProvider:
    """Build the OIDCProxy auth provider for the public MCP server.

    Returns:
        Configured auth provider for the public MCP server.
    """
    (
        public_base_url,
        oidc_config_url,
        client_id,
        client_secret,
    ) = SETTINGS.require_mcp_oauth()

    logger.info(
        "Configuring public MCP OAuth via Authentik OIDC proxy at {}",
        public_base_url,
    )

    return OIDCProxy(
        config_url=oidc_config_url,
        client_id=client_id,
        client_secret=client_secret,
        base_url=public_base_url,
        require_authorization_consent="external",
        allowed_client_redirect_uris=list(_CHATGPT_REDIRECT_URIS),
        required_scopes=["openid"],
    )
