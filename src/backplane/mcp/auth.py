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

from typing import TYPE_CHECKING, Final, Literal, NotRequired, TypedDict, override

from authlib.jose.errors import JoseError
from fastmcp.server.auth import require_scopes
from fastmcp.server.auth.oidc_proxy import OIDCConfiguration, OIDCProxy
from fastmcp.server.auth.providers.introspection import IntrospectionTokenVerifier
from loguru import logger
from mcp.server.auth.middleware.auth_context import AuthContextMiddleware
from mcp.server.auth.middleware.bearer_auth import BearerAuthBackend
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware

from backplane.utils.exceptions import UserError
from backplane.utils.settings import SETTINGS

# Cache introspection briefly so every MCP tool call does not hit Authentik.
_INTROSPECTION_CACHE_TTL_SECONDS: Final = 60

if TYPE_CHECKING:
    from fastmcp.server.auth import AuthProvider
    from fastmcp.utilities.authorization import AuthCheck
    from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
    from mcp.server.auth.provider import AccessToken
    from starlette.authentication import AuthCredentials
    from starlette.requests import HTTPConnection

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


class _LoggingBearerAuthBackend(BearerAuthBackend):
    """Bearer backend that logs missing Authorization headers on ``/mcp``."""

    @override
    async def authenticate(
        self,
        conn: HTTPConnection,
    ) -> tuple[AuthCredentials, AuthenticatedUser] | None:
        auth_header = conn.headers.get("authorization")
        if conn.url.path.rstrip("/").endswith("/mcp") and (
            not auth_header or not auth_header.lower().startswith("bearer ")
        ):
            logger.warning("MCP OAuth: /mcp request missing Bearer Authorization header")
        return await super().authenticate(conn)


class BackplaneOIDCProxy(OIDCProxy):
    """Authentik-aware OIDCProxy with clearer auth failure logging.

    Authentik token introspection often omits ``openid`` from the RFC 7662
    ``scope`` field even when the authorization grant included it. Scope
    checks therefore use the stored upstream token-set ``scope`` from the
    original token response instead of introspection claims.
    """

    @override
    def get_middleware(self) -> list[Middleware]:
        """Return HTTP middleware with bearer auth diagnostics for ``/mcp``."""
        return [
            Middleware(
                AuthenticationMiddleware,
                backend=_LoggingBearerAuthBackend(self),
            ),
            Middleware(AuthContextMiddleware),
        ]

    @override
    async def load_access_token(self, token: str) -> AccessToken | None:
        """Validate a FastMCP token and restore upstream scopes when needed.

        Returns:
            Validated access token metadata, or ``None`` when validation fails.
        """
        validated = await super().load_access_token(token)
        if validated is None:
            await self._log_access_token_rejection(token)
            return None
        return await self._with_upstream_scopes(token, validated)

    async def _with_upstream_scopes(
        self,
        fastmcp_token: str,
        validated: AccessToken,
    ) -> AccessToken:
        upstream_scopes = await self._upstream_granted_scopes(fastmcp_token)
        if not upstream_scopes:
            return validated
        if set(validated.scopes) >= set(upstream_scopes):
            return validated
        return validated.model_copy(update={"scopes": upstream_scopes})

    async def _upstream_granted_scopes(self, fastmcp_token: str) -> list[str]:
        try:
            payload = self.jwt_issuer.verify_token(fastmcp_token)
            jti = payload.get("jti")
            if not isinstance(jti, str):
                return []
            jti_mapping = await self._jti_mapping_store.get(key=jti)
            if jti_mapping is None:
                return []
            upstream = await self._upstream_token_store.get(
                key=jti_mapping.upstream_token_id,
            )
            if upstream is None or not upstream.scope:
                return []
            return upstream.scope.split()
        except (JoseError, KeyError, TypeError, AttributeError) as err:
            logger.warning("MCP OAuth: error verifying FastMCP JWT: {}", err)

            return []

    async def _log_access_token_rejection(self, token: str) -> None:
        if not token:
            logger.warning("MCP OAuth: empty bearer token on /mcp")
            return
        try:
            payload = self.jwt_issuer.verify_token(token)
        except JoseError as exc:
            logger.warning(
                "MCP OAuth: FastMCP JWT rejected (len={}): {}",
                len(token),
                exc,
            )
            return

        jti = payload.get("jti")
        if not isinstance(jti, str):
            logger.warning("MCP OAuth: FastMCP JWT missing jti claim")
            return

        jti_mapping = await self._jti_mapping_store.get(key=jti)
        if jti_mapping is None:
            logger.warning(
                "MCP OAuth: JTI mapping missing for jti={}...",
                jti[:16],
            )
            return

        upstream = await self._upstream_token_store.get(
            key=jti_mapping.upstream_token_id,
        )
        if upstream is None:
            logger.warning(
                "MCP OAuth: upstream token missing for jti={}...",
                jti[:16],
            )
            return

        verification_token = self._get_verification_token(upstream)
        if verification_token is None:
            logger.warning(
                "MCP OAuth: no upstream verification token stored for jti={}...",
                jti[:16],
            )
            return

        logger.warning(
            "MCP OAuth: upstream token verification failed for jti={}...",
            jti[:16],
        )


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

    Raises:
        UserError: When OAuth settings are incomplete or Authentik discovery
            omits a token introspection endpoint.
    """
    (
        public_base_url,
        oidc_config_url,
        client_id,
        client_secret,
    ) = SETTINGS.require_mcp_oauth()

    oidc_config = OIDCConfiguration.get_oidc_configuration(
        oidc_config_url,
        strict=None,
        timeout_seconds=None,
    )
    if not oidc_config.introspection_endpoint:
        msg = (
            "Authentik OIDC provider must expose an introspection endpoint. "
            f"None found in {oidc_config_url}"
        )
        raise UserError(msg)

    logger.info(
        (
            "Configuring public MCP OAuth via Authentik OIDC proxy at {} "
            "(upstream token introspection)"
        ),
        public_base_url,
    )

    # Do not require scopes during introspection: Authentik often omits ``openid``
    # from the RFC 7662 scope field. Scopes are restored from the token response
    # stored during code exchange (see BackplaneOIDCProxy._with_upstream_scopes).
    token_verifier = IntrospectionTokenVerifier(
        introspection_url=str(oidc_config.introspection_endpoint),
        client_id=client_id,
        client_secret=client_secret,
        client_auth_method="client_secret_post",
        required_scopes=None,
        cache_ttl_seconds=_INTROSPECTION_CACHE_TTL_SECONDS,
    )

    auth_provider = BackplaneOIDCProxy(
        config_url=oidc_config_url,
        client_id=client_id,
        client_secret=client_secret,
        base_url=public_base_url,
        require_authorization_consent="external",
        allowed_client_redirect_uris=list(_CHATGPT_REDIRECT_URIS),
        token_verifier=token_verifier,
    )
    auth_provider.required_scopes = [MCP_BASELINE_SCOPE]
    auth_provider.update_default_scopes([MCP_BASELINE_SCOPE])
    return auth_provider
