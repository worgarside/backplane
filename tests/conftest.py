"""Shared test fixtures."""

from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

import pytest

from backplane.utils.async_path import AsyncPath
from backplane.utils.settings import SETTINGS, VAULT_PATHS

DOMAIN_TEMPLATE = """---
type: domain
status: active
created: "{ date:YYYY-MM-DDTHH:mm:ss }"
updated: "{ date:YYYY-MM-DDTHH:mm:ss }"
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
created: "{ date:YYYY-MM-DDTHH:mm:ss }"
updated: "{ date:YYYY-MM-DDTHH:mm:ss }"
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
created: "{ date:YYYY-MM-DDTHH:mm:ss }"
updated: "{ date:YYYY-MM-DDTHH:mm:ss }"
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

PROJECT_BOARD = """---

kanban-plugin: board

---

## Backlog



## Todo
"""

PROJECT_TEMPLATE = """---
type: project
status: planning
created: "{ date:YYYY-MM-DDTHH:mm:ss }"
updated: "{ date:YYYY-MM-DDTHH:mm:ss }"
domains: []
resources: []
people: []
priority: medium
due:
completed:
tags:
  - project
---
# {{title}}

## Overview

## Goals

-

## Tasks

-

## Notes
"""

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def vault_path(tmp_path: Path) -> AsyncPath:
    """Provide a temporary vault root for path-resolution tests."""
    return AsyncPath(tmp_path)


@pytest.fixture
def obsidian_vault(
    vault_path: AsyncPath,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncPath:
    """
    Create a temporary Obsidian vault with entity templates and a project board.
    
    Returns:
        AsyncPath: The vault root path.
    """
    monkeypatch.setattr(SETTINGS, "obsidian_vault_path", vault_path)
    _install_entity_templates(vault_path)
    _install_project_board(vault_path)
    return vault_path


def _install_entity_templates(vault_path: AsyncPath) -> None:
    """
    Create entity template files in the vault's Templates directory.
    
    Writes Domain.md, Person.md, Project.md, and Resource.md files using the
    corresponding template constants.
    """
    templates = pathlib.Path(str(vault_path)) / "Templates"
    templates.mkdir(parents=True, exist_ok=True)
    _ = (templates / "Domain.md").write_text(DOMAIN_TEMPLATE, encoding="utf-8")
    _ = (templates / "Person.md").write_text(PERSON_TEMPLATE, encoding="utf-8")
    _ = (templates / "Project.md").write_text(PROJECT_TEMPLATE, encoding="utf-8")
    _ = (templates / "Resource.md").write_text(RESOURCE_TEMPLATE, encoding="utf-8")


def _install_project_board(vault_path: AsyncPath) -> None:
    """
    Create the project board file in the vault using the minimal Kanban board template.
    """
    board = pathlib.Path(str(vault_path)) / str(VAULT_PATHS.project_board_path)
    board.parent.mkdir(parents=True, exist_ok=True)
    _ = board.write_text(PROJECT_BOARD, encoding="utf-8")
