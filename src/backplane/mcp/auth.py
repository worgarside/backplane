"""OAuth authentication for the public Backplane MCP server."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, NotRequired, TypedDict

from fastmcp.server.auth import require_scopes
from fastmcp.server.auth.oidc_proxy import OIDCProxy
from loguru import logger

from backplane.utils.settings import SETTINGS

if TYPE_CHECKING:
    from fastmcp.server.auth import AuthProvider
    from fastmcp.utilities.authorization import AuthCheck

_CHATGPT_REDIRECT_URIS: tuple[str, ...] = (
    "https://chatgpt.com/connector/oauth/*",
    "https://chatgpt.com/connector_platform_oauth_redirect",
)


class OAuthSecurityScheme(TypedDict):
    """OAuth2 security scheme advertised to ChatGPT MCP clients."""

    type: Literal["oauth2"]
    scopes: list[str]


class OAuthToolMeta(TypedDict):
    """MCP tool metadata that advertises OAuth requirements."""

    securitySchemes: list[OAuthSecurityScheme]


class OAuthToolRegistrationKwargs(TypedDict):
    """FastMCP tool/resource registration kwargs for OAuth-protected components."""

    auth: NotRequired[AuthCheck]
    meta: NotRequired[dict[str, list[OAuthSecurityScheme]]]


def oauth_tool_meta() -> OAuthToolMeta:
    """Return MCP tool metadata that advertises OAuth to ChatGPT."""
    return {
        "securitySchemes": [{"type": "oauth2", "scopes": ["openid"]}],
    }


def oauth_tool_registration_kwargs() -> OAuthToolRegistrationKwargs:
    """Return FastMCP registration kwargs for OAuth-protected tools and resources."""
    tool_meta = oauth_tool_meta()
    return {
        "auth": require_scopes("openid"),
        "meta": {"securitySchemes": tool_meta["securitySchemes"]},
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
