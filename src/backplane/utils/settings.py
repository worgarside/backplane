"""Application settings for Backplane."""

from __future__ import annotations

import zoneinfo
from typing import Annotated, Final, final

import anyio
import yarl
from pydantic import BeforeValidator, Field, field_validator
from pydantic_settings import BaseSettings


def _parse_timezone(v: object) -> zoneinfo.ZoneInfo:
    if isinstance(v, zoneinfo.ZoneInfo):
        return v
    try:
        return zoneinfo.ZoneInfo(str(v))
    except zoneinfo.ZoneInfoNotFoundError as exc:
        msg = f"invalid timezone {v!r}: provide a valid IANA timezone name, e.g. 'Europe/London'"
        raise ValueError(msg) from exc


def _parse_obsidian_vault_path(v: object) -> anyio.Path:
    if isinstance(v, anyio.Path):
        return v
    if isinstance(v, str):
        return anyio.Path(v)
    msg = "obsidian_vault_path must be a string or anyio.Path"
    raise TypeError(msg)


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
        BeforeValidator(_parse_obsidian_vault_path),
        Field(description="Absolute path to the Obsidian vault directory."),
    ]


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


SETTINGS = Settings()  # pyright: ignore[reportCallIssue]
VAULT_PATHS: Final = VaultPaths()


__all__ = ["SETTINGS", "VAULT_PATHS", "VaultPaths"]
