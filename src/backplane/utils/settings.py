"""Application settings for Backplane."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import BeforeValidator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Settings for the Backplane application."""

    obsidian_vault_path: Annotated[
        Path,
        BeforeValidator(lambda x: Path(x) if isinstance(x, str) else x),  # pyright: ignore[reportAny]
    ]


SETTINGS = Settings()  # pyright: ignore[reportCallIssue]


__all__ = ["SETTINGS"]
