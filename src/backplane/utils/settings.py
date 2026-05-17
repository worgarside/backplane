"""Application settings for Backplane."""

from __future__ import annotations

import zoneinfo
from typing import Annotated

import anyio
from pydantic import BeforeValidator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Settings for the Backplane application."""

    obsidian_vault_path: Annotated[
        anyio.Path,
        BeforeValidator(lambda x: anyio.Path(x) if isinstance(x, str) else x),  # pyright: ignore[reportAny]
    ]
    local_timezone: Annotated[
        zoneinfo.ZoneInfo,
        BeforeValidator(zoneinfo.ZoneInfo),
    ] = zoneinfo.ZoneInfo("Europe/London")


SETTINGS = Settings()  # pyright: ignore[reportCallIssue]


__all__ = ["SETTINGS"]
