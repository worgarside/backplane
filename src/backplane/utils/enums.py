"""Enumerations for common values."""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from .settings import VAULT_PATHS

if TYPE_CHECKING:
    import anyio


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


class VaultEntityKind(enum.StrEnum):
    """Vault entity note kinds under Domains, People, Projects, or Resources."""

    DOMAIN = enum.auto()
    PERSON = enum.auto()
    PROJECT = enum.auto()
    RESOURCE = enum.auto()

    @property
    def vault_dir(self) -> anyio.Path:
        """Return the vault subdirectory for this entity kind."""
        return {
            VaultEntityKind.DOMAIN: VAULT_PATHS.domains_dir,
            VaultEntityKind.PERSON: VAULT_PATHS.people_dir,
            VaultEntityKind.PROJECT: VAULT_PATHS.projects_dir,
            VaultEntityKind.RESOURCE: VAULT_PATHS.resources_dir,
        }[self]
