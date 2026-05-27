"""Enumerations for common values."""

from __future__ import annotations

import enum


class Effort(enum.StrEnum):
    """Task effort levels."""

    SMALL = enum.auto()
    MEDIUM = enum.auto()
    LARGE = enum.auto()


class Priority(enum.StrEnum):
    """Task priority levels."""

    LOW = enum.auto()
    MEDIUM = enum.auto()
    HIGH = enum.auto()
