"""Application settings for Backplane."""

from __future__ import annotations

import zoneinfo
from typing import Annotated, Final, final

import anyio
import yarl
from pydantic import BeforeValidator, Field, AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings


def _parse_timezone(v: object) -> zoneinfo.ZoneInfo:
    if isinstance(v, zoneinfo.ZoneInfo):
        return v
    try:
        return zoneinfo.ZoneInfo(str(v))
    except zoneinfo.ZoneInfoNotFoundError as exc:
        msg = f"invalid timezone {v!r}: provide a valid IANA timezone name, e.g. 'Europe/London'"
        raise ValueError(msg) from exc


_MCP_OAUTH_REQUIRED_MSG = (
    "Public MCP requires OAuth. Set MCP_PUBLIC_BASE_URL, "
    "MCP_OIDC_CONFIG_URL, MCP_OIDC_CLIENT_ID, and MCP_OIDC_CLIENT_SECRET."
)


class Settings(BaseSettings):
    """Settings for the Backplane application."""

    local_timezone: Annotated[
        zoneinfo.ZoneInfo,
        BeforeValidator(_parse_timezone),
        Field(
            description=(
                "IANA timezone used for date/timestamp calculations, e.g. 'Europe/London'. "
                "Overridable via the LOCAL_TIMEZONE environment variable."
            ),
        ),
    ] = zoneinfo.ZoneInfo("Europe/London")

    # ========================================================================
    # Home Assistant

    home_assistant_url: Annotated[
        yarl.URL | None,
        Field(
            default=None,
            description="Base URL of the Home Assistant instance, e.g. http://homeassistant.local:8123.",
        ),
    ]

    home_assistant_token: Annotated[
        str | None,
        Field(
            default=None,
            description="Long-lived access token for the Home Assistant REST API.",
        ),
    ]

    home_assistant_mcp_entry_id: Annotated[
        str | None,
        Field(
            default=None,
            description="Config entry ID of the Backplane MCP integration in Home Assistant.",
        ),
    ]

    @field_validator("home_assistant_url", mode="before")
    @classmethod
    def _parse_ha_url(cls, v: yarl.URL | str | None) -> yarl.URL | None:
        if v is None:
            return None
        if isinstance(v, yarl.URL):
            return v
        return yarl.URL(v.rstrip("/"))

    # ========================================================================
    # LLM

    task_metadata_model: Annotated[
        str,
        Field(
            description=(
                "PydanticAI model string used for task metadata extraction, "
                "e.g. 'anthropic:claude-haiku-4-5-20251001' or 'openai:gpt-4o-mini'."
            ),
        ),
    ] = "openai:gpt-4o-mini"

    # ========================================================================
    # Obsidian

    obsidian_vault_path: Annotated[
        anyio.Path,
        Field(description="Absolute path to the Obsidian vault directory."),
    ]

    @field_validator("obsidian_vault_path", mode="before")
    @classmethod
    def _parse_obsidian_vault_path(cls, v: anyio.Path | str) -> anyio.Path:
        if isinstance(v, anyio.Path):
            return v
        return anyio.Path(v)

    # ========================================================================
    # Public MCP OAuth (Authentik via FastMCP OIDCProxy)

    mcp_public_base_url: Annotated[
        AnyHttpUrl | None,
        Field(
            default=None,
            description=(
                "Public HTTPS base URL of the ChatGPT-facing MCP server, "
                "e.g. https://backplane-mcp.example.com."
            ),
        ),
    ]

    mcp_oidc_config_url: Annotated[
        AnyHttpUrl | None,
        Field(
            default=None,
            description=(
                "Authentik OIDC discovery URL for the Backplane MCP application, "
                "e.g. https://auth.example.com/application/o/backplane-mcp/"
                ".well-known/openid-configuration."
            ),
        ),
    ]

    mcp_oidc_client_id: Annotated[
        str | None,
        Field(
            default=None,
            description="OAuth client ID from the Authentik Backplane MCP provider.",
        ),
    ]

    mcp_oidc_client_secret: Annotated[
        str | None,
        Field(
            default=None,
            description="OAuth client secret from the Authentik Backplane MCP provider.",
        ),
    ]

    @property
    def mcp_oauth_configured(self) -> bool:
        """Return whether the public MCP OAuth settings are complete."""
        return (
            self.mcp_public_base_url is not None
            and self.mcp_oidc_config_url is not None
            and self.mcp_oidc_client_id is not None
            and self.mcp_oidc_client_secret is not None
        )

    def require_mcp_oauth(self) -> tuple[AnyHttpUrl, AnyHttpUrl, str, str]:
        """Return validated public MCP OAuth settings.

        Returns:
            Public base URL, OIDC discovery URL, client ID, and client secret.

        Raises:
            ValueError: If any required OAuth setting is missing.
        """
        public_base_url = self.mcp_public_base_url
        oidc_config_url = self.mcp_oidc_config_url
        client_id = self.mcp_oidc_client_id
        client_secret = self.mcp_oidc_client_secret
        if (
            public_base_url is None
            or oidc_config_url is None
            or client_id is None
            or client_secret is None
        ):
            raise ValueError(_MCP_OAUTH_REQUIRED_MSG)

        return public_base_url, oidc_config_url, client_id, client_secret


@final
class VaultPaths:
    """Stable relative paths within the Obsidian vault."""

    daily_notes_dir: Final = anyio.Path("Daily Notes")
    domains_dir: Final = anyio.Path("Domains")
    inbox_dir: Final = anyio.Path("Inbox")
    people_dir: Final = anyio.Path("People")
    resources_dir: Final = anyio.Path("Resources")
    tasks_dir: Final = anyio.Path("Tasks")
    task_notes_dir: Final = anyio.Path("Tasks") / "Tasks"
    task_board_path: Final = anyio.Path("Tasks") / "Board.md"


SETTINGS: Final = Settings()  # pyright: ignore[reportCallIssue]
VAULT_PATHS: Final = VaultPaths()


__all__ = ["SETTINGS", "VAULT_PATHS", "VaultPaths"]
