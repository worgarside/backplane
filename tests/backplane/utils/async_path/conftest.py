"""Shared fixtures for AsyncPath tests."""

from __future__ import annotations

from pydantic import BaseModel

from backplane.utils.async_path import AsyncPath


class SampleMetadata(BaseModel, frozen=True):
    """Minimal model for exercising AsyncPath field validation."""

    path: AsyncPath
