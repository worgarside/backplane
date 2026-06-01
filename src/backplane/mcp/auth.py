"""OAuth authentication for the public Backplane MCP server.

Scope model (current):
    The public MCP server requires authentication globally. All tools and
    resources registered with ``require_oauth=True`` use a single baseline
    scope: ``openid``.

Future (deferred):
    A fuller MCP design may split read vs write tools using ``mcp.read`` and
    ``mcp.write``. Do not add that split until the live ChatGPT → FastMCP →
    Authentik flow is verified and we know which scopes are requested, issued,
    preserved, and visible to ``require_scopes`` during tool execution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Literal, NotRequired, TypedDict

from fastmcp.server.auth import require_scopes
from fastmcp.server.auth.oidc_proxy import OIDCProxy
from loguru import logger

from backplane.utils.settings import SETTINGS

if TYPE_CHECKING:
    from fastmcp.server.auth import AuthProvider
    from fastmcp.utilities.authorization import AuthCheck

MCP_BASELINE_SCOPE: Final = "openid"

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


def oauth_tool_meta(*scopes: str) -> OAuthToolMeta:
    """Return MCP tool metadata that advertises OAuth to ChatGPT.

    Args:
        scopes: OAuth scopes to advertise. Defaults to ``MCP_BASELINE_SCOPE``.
    """
    effective_scopes = list(scopes) if scopes else [MCP_BASELINE_SCOPE]
    return {
        "securitySchemes": [{"type": "oauth2", "scopes": effective_scopes}],
    }


def oauth_tool_registration_kwargs(
    *scopes: str,
) -> OAuthToolRegistrationKwargs:
    """Return FastMCP registration kwargs for OAuth-protected tools and resources.

    Args:
        scopes: Required OAuth scopes for the component. Defaults to
            ``MCP_BASELINE_SCOPE`` when omitted.
    """
    effective_scopes = scopes or (MCP_BASELINE_SCOPE,)
    tool_meta = oauth_tool_meta(*effective_scopes)
    return {
        "auth": require_scopes(*effective_scopes),
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
        required_scopes=[MCP_BASELINE_SCOPE],
    )
