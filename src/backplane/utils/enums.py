"""Enumerations for common values."""

from __future__ import annotations

import enum


class Priority(enum.StrEnum):
    """Task priority levels."""

    LOW = enum.auto()
    MEDIUM = enum.auto()
    HIGH = enum.auto()
