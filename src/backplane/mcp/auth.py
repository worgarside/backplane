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

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final, Literal, NotRequired, TypedDict, override
from urllib.parse import parse_qs

from authlib.jose.errors import JoseError
from fastmcp.server.auth import require_scopes
from fastmcp.server.auth.auth import PrivateKeyJWTClientAuthenticator, TokenHandler
from fastmcp.server.auth.oidc_proxy import OIDCConfiguration, OIDCProxy
from fastmcp.server.auth.providers.introspection import IntrospectionTokenVerifier
from loguru import logger
from mcp.server.auth.handlers.token import TokenErrorResponse, TokenSuccessResponse
from mcp.server.auth.json_response import PydanticJSONResponse
from mcp.server.auth.middleware.client_auth import ClientAuthenticator
from mcp.server.auth.routes import build_metadata
from mcp.server.auth.settings import ClientRegistrationOptions, RevocationOptions
from mcp.shared.auth import OAuthToken
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from backplane.utils.exceptions import UserError
from backplane.utils.settings import SETTINGS

# Cache introspection briefly so every MCP tool call does not hit Authentik.
_INTROSPECTION_CACHE_TTL_SECONDS: Final = 60

if TYPE_CHECKING:
    from fastmcp.server.auth import AuthProvider
    from fastmcp.utilities.authorization import AuthCheck
    from mcp.server.auth.provider import AccessToken

MCP_BASELINE_SCOPE: Final = "openid"

# Requested on /authorize so Authentik returns a refresh token upstream; FastMCP
# then includes refresh_token in /token responses (required for ChatGPT MCP).
MCP_AUTHORIZE_SCOPES: Final[tuple[str, ...]] = (MCP_BASELINE_SCOPE, "offline_access")


def _add_mcp_path_oauth_authorization_server_metadata_route(
    routes: list[Route],
    mcp_path: str | None,
) -> list[Route]:
    """Expose authorization-server metadata at the resource-specific well-known path.

    Some clients (including ChatGPT) request
    ``/.well-known/oauth-authorization-server/mcp`` when the MCP resource is
    ``/mcp``. FastMCP only registers the host-level path by default.
    """
    if not mcp_path:
        return routes

    path_suffix = mcp_path.rstrip("/")
    if not path_suffix or path_suffix == "/":
        return routes

    resource_metadata_path = (
        f"/.well-known/oauth-authorization-server{path_suffix}"
    )
    if any(route.path == resource_metadata_path for route in routes):
        return routes

    for route in routes:
        if route.path != "/.well-known/oauth-authorization-server":
            continue
        if route.endpoint is None or route.methods is None:
            break
        routes.append(
            Route(
                path=resource_metadata_path,
                endpoint=route.endpoint,
                methods=list(route.methods),
                name=route.name,
                include_in_schema=route.include_in_schema,
            ),
        )
        break

    return routes


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


class _OAuthTokenWithResource(OAuthToken):
    """Token response that may include an RFC 8707 resource indicator."""

    resource: str | None = None


def _first_urlencoded_value(parsed: dict[str, list[str]], key: str) -> str | None:
    values = parsed.get(key)
    if not values:
        return None
    value = values[0].strip()
    return value or None


def _request_with_replayed_body(request: Request, body: bytes) -> Request:
    """Return a request whose body can be read again (e.g. by ``request.form()``)."""

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(request.scope, receive)


@dataclass
class _ResourceEchoTokenHandler(TokenHandler):
    """Token handler that echoes RFC 8707 ``resource`` in successful responses."""

    default_resource_url: str | None = None
    _requested_resource: str | None = field(default=None, init=False, repr=False)

    @override
    async def handle(self, request: Request) -> PydanticJSONResponse:
        self._requested_resource = None
        if request.method == "POST":
            # Read the body once here; a second ``request.form()`` on the same
            # request would be empty and break client_id validation downstream.
            body = await request.body()
            parsed = parse_qs(body.decode(), keep_blank_values=True)
            self._requested_resource = _first_urlencoded_value(parsed, "resource")
            request = _request_with_replayed_body(request, body)
        return await TokenHandler.handle(self, request)

    @override
    def response(
        self,
        obj: TokenSuccessResponse | TokenErrorResponse,
    ) -> PydanticJSONResponse:
        if isinstance(obj, TokenErrorResponse):
            return TokenHandler.response(self, obj)

        resource = self._requested_resource or self.default_resource_url
        token = obj.root
        if resource is None:
            return TokenHandler.response(self, obj)

        extended = _OAuthTokenWithResource(
            access_token=token.access_token,
            token_type=token.token_type,
            expires_in=token.expires_in,
            scope=token.scope,
            refresh_token=token.refresh_token,
            resource=resource,
        )
        return PydanticJSONResponse(
            content=extended,
            status_code=200,
            headers={
                "Cache-Control": "no-store",
                "Pragma": "no-cache",
            },
        )


class BackplaneOIDCProxy(OIDCProxy):
    """Authentik-aware OIDCProxy.

    Authentik token introspection often omits ``openid`` from the RFC 7662
    ``scope`` field even when the authorization grant included it. Scope
    checks therefore use the stored upstream token-set ``scope`` from the
    original token response instead of introspection claims.
    """

    @override
    def get_routes(self, mcp_path: str | None = None) -> list[Route]:
        """Add ChatGPT-facing discovery routes and RFC 8707 token responses."""
        routes = self._replace_token_route(super().get_routes(mcp_path))
        oidc_document = self._openid_configuration_document()

        async def openid_configuration(_: Request) -> Response:
            return JSONResponse(
                content=oidc_document,
                headers={"Cache-Control": "public, max-age=3600"},
            )

        async def jwks(_: Request) -> Response:
            return JSONResponse(
                content={"keys": []},
                headers={"Cache-Control": "public, max-age=3600"},
            )

        routes.extend(
            [
                Route(
                    "/.well-known/openid-configuration",
                    endpoint=openid_configuration,
                    methods=["GET"],
                ),
                Route(
                    "/.well-known/jwks.json",
                    endpoint=jwks,
                    methods=["GET"],
                ),
            ],
        )
        routes = _add_mcp_path_oauth_authorization_server_metadata_route(
            routes,
            mcp_path,
        )
        return routes

    def _openid_configuration_document(self) -> dict[str, object]:
        """Build OIDC Provider Metadata for the FastMCP OAuth proxy."""
        if self.base_url is None:
            msg = "OAuth base_url must be configured before building OIDC metadata"
            raise UserError(msg)

        registration_options = (
            self.client_registration_options or ClientRegistrationOptions()
        )
        revocation_options = self.revocation_options or RevocationOptions()
        metadata = build_metadata(
            issuer_url=self.base_url,
            service_documentation_url=self.service_documentation_url,
            client_registration_options=registration_options,
            revocation_options=revocation_options,
        )
        document: dict[str, object] = metadata.model_dump(mode="json", exclude_none=True)
        prefix = str(self.base_url).rstrip("/")
        document["jwks_uri"] = f"{prefix}/.well-known/jwks.json"
        document["subject_types_supported"] = ["public"]
        document["id_token_signing_alg_values_supported"] = ["HS256"]
        document["client_id_metadata_document_supported"] = True
        document["scopes_supported"] = list(MCP_AUTHORIZE_SCOPES)
        return document

    def _replace_token_route(self, routes: list[Route]) -> list[Route]:
        """Wrap ``/token`` so successful responses echo the RFC 8707 resource."""
        updated: list[Route] = []
        for route in routes:
            if not (
                route.path == "/token"
                and route.methods is not None
                and "POST" in route.methods
            ):
                updated.append(route)
                continue

            token_handler = self._build_resource_echo_token_handler()
            updated.append(
                Route(
                    path="/token",
                    endpoint=token_handler.handle,
                    methods=["POST"],
                    name=route.name,
                    include_in_schema=route.include_in_schema,
                ),
            )
        return updated

    def _build_resource_echo_token_handler(self) -> _ResourceEchoTokenHandler:
        client_authenticator = ClientAuthenticator(self)
        if self._cimd_manager is not None:
            token_endpoint_url = f"{self.base_url}/token"
            client_authenticator = PrivateKeyJWTClientAuthenticator(
                provider=self,
                cimd_manager=self._cimd_manager,
                token_endpoint_url=token_endpoint_url,
            )

        return _ResourceEchoTokenHandler(
            provider=self,
            client_authenticator=client_authenticator,
            default_resource_url=(
                str(self._resource_url) if self._resource_url is not None else None
            ),
        )

    @override
    async def load_access_token(self, token: str) -> AccessToken | None:
        """Validate a FastMCP token and restore upstream scopes when needed.

        Returns:
            Validated access token metadata, or ``None`` when validation fails.
        """
        validated = await super().load_access_token(token)
        if validated is None:
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
        except (JoseError, KeyError, TypeError, AttributeError):
            return []


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
        "Configuring public MCP OAuth via Authentik OIDC proxy at {}",
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
        allowed_client_redirect_uris=SETTINGS.allowed_client_redirect_uri_patterns,
        token_verifier=token_verifier,
    )
    auth_provider.required_scopes = [MCP_BASELINE_SCOPE]
    auth_provider.update_default_scopes(list(MCP_AUTHORIZE_SCOPES))
    return auth_provider
