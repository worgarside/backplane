"""Shared test fixtures."""

from __future__ import annotations

from typing import TYPE_CHECKING

import anyio
import pytest

from backplane.utils.helpers.files import atomic_write_text
from backplane.utils.settings import SETTINGS

DOMAIN_TEMPLATE = """---
type: domain
status: active
created:
  "{ date:YYYY-MM-DDTHH:mm:ss }":
updated:
  "{ date:YYYY-MM-DDTHH:mm:ss }":
tags:
  - domain
---
# {{title}}

## Overview

## Key Resources

-

## Active Projects

-

## Related Tasks

-

## Notes
"""

PERSON_TEMPLATE = """---
type: person
status: active
created:
  "{ date:YYYY-MM-DDTHH:mm:ss }":
updated:
  "{ date:YYYY-MM-DDTHH:mm:ss }":
tags:
  - person
---
# {{title}}

## Overview

## Context

## Related Tasks

-

## Notes
"""

RESOURCE_TEMPLATE = """---
type: resource
status: active
created:
  "{ date:YYYY-MM-DDTHH:mm:ss }":
updated:
  "{ date:YYYY-MM-DDTHH:mm:ss }":
domains: []
url:
tags:
  - resource
---
# {{title}}

## Overview

## Links

-

## Related Tasks

-

## Notes
"""

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def vault_path(tmp_path: Path) -> anyio.Path:
    """Provide a temporary vault root for path-resolution tests."""
    return anyio.Path(tmp_path)


@pytest.fixture
def obsidian_vault(
    vault_path: anyio.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> anyio.Path:
    """Point application settings at a temporary vault root."""
    monkeypatch.setattr(SETTINGS, "obsidian_vault_path", vault_path)
    return vault_path


@pytest.fixture
async def entity_templates(obsidian_vault: anyio.Path) -> None:
    """Install minimal entity templates in the temporary vault."""
    templates = obsidian_vault / "Templates"
    await templates.mkdir(parents=True, exist_ok=True)
    await atomic_write_text(templates / "Domain.md", DOMAIN_TEMPLATE)
    await atomic_write_text(templates / "Person.md", PERSON_TEMPLATE)
    await atomic_write_text(templates / "Resource.md", RESOURCE_TEMPLATE)
