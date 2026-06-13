"""MCP tools for vault entity notes (Domains, People, Resources)."""

from __future__ import annotations

import json
import pathlib
import re
from typing import TYPE_CHECKING, Annotated, Literal

from loguru import logger
from pydantic import Field

from backplane.mcp.auth import OAuthToolRegistrationKwargs, oauth_tool_registration_kwargs
from backplane.services.vault_entities import UpdateMode, VaultEntityService
from backplane.utils.enums import VaultEntityKind
from backplane.utils.settings import SETTINGS

if TYPE_CHECKING:
    from fastmcp import FastMCP

_HEADING_LINE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_CODE_FENCE = re.compile(r"^\s*```")
VaultEntityKindParam = Literal["domain", "person", "resource"]


def _format_template_heading_tree(template_text: str) -> str:
    """Parse template markdown for headings and return an indented bullet tree.

    Returns:
        Indented bullet list of headings, or a fallback message.
    """
    in_code = False
    lines: list[str] = []
    for line in template_text.splitlines():
        if _CODE_FENCE.match(line):
            in_code = not in_code
            continue
        if in_code:
            continue
        match = _HEADING_LINE.match(line)
        if match is None:
            continue
        level = len(match.group(1))
        if level == 1:
            continue
        indent = "  " * (level - 2)
        lines.append(f"{indent}- {match.group(2)}")

    return "\n".join(lines) if lines else "(template has no sub-sections)"


def _build_update_description(section_trees: dict[VaultEntityKind, str]) -> str:
    """Build the update tool description with per-kind section structures.

    Returns:
        Tool description text for ``update_vault_entity``.
    """
    lines = [
        "Update a section of a vault entity note (Domain, Person, or Resource).",
        "",
        "Use append for most captures; replace only when the user asks to overwrite.",
        "",
        "Section structures by kind (prefer these names verbatim):",
    ]
    for kind in VaultEntityKind:
        lines.extend(
            (
                "",
                f"{kind.value.title()} sections:",
                section_trees[kind],
            ),
        )
    lines.extend(
        (
            "",
            "If the section is missing, set `create_section_if_not_exists=true` to create it.",
        ),
    )
    return "\n".join(lines)


_LIST_DESCRIPTION = (
    "List display names of vault entity notes for a given kind.\n\n"
    "Domains are platforms or broad areas. Resources are specific integrations, "
    "APIs, vendors, or services. People are collaborators or contacts referenced "
    "in related work."
)
_LIST_SECTIONS_DESCRIPTION = (
    "List sections in a vault entity note. Use before reading or updating a "
    "specific section when you need to know the available headings. Returns JSON "
    "section metadata in document order, with paths relative to the note title."
)
_GET_DESCRIPTION = (
    "Read a vault entity note as rendered markdown. Use when the user asks about "
    "a domain, person, or resource note's contents."
)
_GET_SECTION_DESCRIPTION = (
    "Read a single section of a vault entity note as rendered markdown. Use when "
    "the user needs specific context from a domain, person, or resource note "
    "without loading the whole note."
)
_CREATE_DESCRIPTION = (
    "Create a new vault entity note from the vault template.\n\n"
    "Domains are platforms or broad areas. Resources are specific integrations, "
    "APIs, vendors, or services — never duplicate the same name as a domain. "
    "People are individuals referenced in related work.\n\n"
    "Fails if a note with the same name already exists."
)


async def list_vault_entities(
    kind: Annotated[
        VaultEntityKindParam,
        Field(description="Entity kind to list: domain, person, or resource."),
    ],
) -> str:
    """List display names of vault entity notes.

    Args:
        kind: Entity kind to list.

    Returns:
        JSON array of display names sorted alphabetically.
    """
    logger.info("list_vault_entities: kind={}", kind)
    names = await VaultEntityService.list_entities(VaultEntityKind(kind))
    return json.dumps(names)


async def list_vault_entity_sections(
    kind: Annotated[
        VaultEntityKindParam,
        Field(description="Entity kind: domain, person, or resource."),
    ],
    name: Annotated[
        str,
        Field(description="Human-readable entity name, e.g. 'Home Assistant'."),
    ],
) -> str:
    """List sections in a vault entity note.

    Args:
        kind: Entity kind.
        name: Human-readable entity name.

    Returns:
        JSON array of section metadata in document order.
    """
    logger.info("list_vault_entity_sections: kind={} name={!r}", kind, name)
    sections = await VaultEntityService.list_entity_sections(
        VaultEntityKind(kind),
        name,
    )
    return json.dumps(sections)


async def get_vault_entity(
    kind: Annotated[
        VaultEntityKindParam,
        Field(description="Entity kind: domain, person, or resource."),
    ],
    name: Annotated[
        str,
        Field(description="Human-readable entity name, e.g. 'Home Assistant'."),
    ],
) -> str:
    """Read a vault entity note.

    Args:
        kind: Entity kind.
        name: Human-readable entity name.

    Returns:
        The entity note rendered as markdown.
    """
    logger.info("get_vault_entity: kind={} name={!r}", kind, name)
    return await VaultEntityService.get_entity(VaultEntityKind(kind), name)


async def get_vault_entity_section(
    *,
    kind: Annotated[
        VaultEntityKindParam,
        Field(description="Entity kind: domain, person, or resource."),
    ],
    name: Annotated[
        str,
        Field(description="Human-readable entity name, e.g. 'Home Assistant'."),
    ],
    section: Annotated[
        str,
        Field(description="Top-level section heading to read, e.g. 'Overview'."),
    ],
) -> str:
    """Read one section of a vault entity note.

    Args:
        kind: Entity kind.
        name: Human-readable entity name.
        section: Top-level section heading to read.

    Returns:
        The requested section rendered as markdown.
    """
    logger.info(
        "get_vault_entity_section: kind={} name={!r} section={!r}",
        kind,
        name,
        section,
    )
    return await VaultEntityService.get_entity_section(
        VaultEntityKind(kind),
        name,
        section=section,
    )


async def create_vault_entity(
    kind: Annotated[
        VaultEntityKindParam,
        Field(description="Entity kind: domain, person, or resource."),
    ],
    name: Annotated[
        str,
        Field(description="Human-readable entity name used as the note title."),
    ],
) -> str:
    """Create a new vault entity note from the vault template.

    Args:
        kind: Entity kind.
        name: Human-readable entity name.

    Returns:
        Short confirmation with the vault-relative path.
    """
    logger.info("create_vault_entity: kind={} name={!r}", kind, name)
    path = await VaultEntityService.create_entity(VaultEntityKind(kind), name)
    return f"Created {kind} {name!r} at {path}."


async def update_vault_entity(
    *,
    kind: Annotated[
        VaultEntityKindParam,
        Field(description="Entity kind: domain, person, or resource."),
    ],
    name: Annotated[
        str,
        Field(description="Human-readable entity name, e.g. 'Home Assistant'."),
    ],
    section: Annotated[
        str,
        Field(
            description="Top-level section heading to update, e.g. 'Overview' or 'Notes'.",
        ),
    ],
    content: Annotated[
        str,
        Field(description="Markdown content to add or replace in the section."),
    ],
    mode: Annotated[
        UpdateMode,
        Field(
            description=(
                "How to combine content with existing section text. append is usually best."
            ),
        ),
    ] = "append",
    create_section_if_not_exists: Annotated[
        bool,
        Field(
            description=(
                "Create the section when missing. Use true when the user explicitly asks "
                "for a new section or after a missing-section error."
            ),
        ),
    ] = False,
) -> str:
    """Update a section of a vault entity note.

    Args:
        kind: Entity kind.
        name: Human-readable entity name.
        section: Top-level section heading to update.
        content: Markdown content to combine with the section.
        mode: How to combine content with existing section text.
        create_section_if_not_exists: Create the section when missing.

    Returns:
        The updated section rendered as markdown.
    """
    logger.info(
        "update_vault_entity: kind={} name={!r} section={!r} mode={}",
        kind,
        name,
        section,
        mode,
    )
    return await VaultEntityService.update_entity(
        VaultEntityKind(kind),
        name,
        section=section,
        content=content,
        mode=mode,
        create_section_if_not_exists=create_section_if_not_exists,
    )


def _load_section_trees() -> dict[VaultEntityKind, str]:
    """Return per-kind section trees loaded synchronously at registration time."""
    trees: dict[VaultEntityKind, str] = {}
    for kind in VaultEntityKind:
        template_rel = VaultEntityService.template_path_for(kind)
        template_path = pathlib.Path(str(SETTINGS.obsidian_vault_path)) / template_rel
        try:
            template_text = template_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            trees[kind] = "(template structure unavailable)"
            continue
        trees[kind] = _format_template_heading_tree(template_text)
    return trees


def register_vault_entity_tools(
    mcp: FastMCP[None],
    *,
    require_oauth: bool = False,
) -> None:
    """Register vault entity tools on a FastMCP server instance."""
    auth_kwargs: OAuthToolRegistrationKwargs = {}
    if require_oauth:
        auth_kwargs = oauth_tool_registration_kwargs()

    update_description = _build_update_description(_load_section_trees())

    _ = mcp.tool(description=_LIST_DESCRIPTION, **auth_kwargs)(list_vault_entities)
    _ = mcp.tool(description=_LIST_SECTIONS_DESCRIPTION, **auth_kwargs)(
        list_vault_entity_sections,
    )
    _ = mcp.tool(description=_GET_DESCRIPTION, **auth_kwargs)(get_vault_entity)
    _ = mcp.tool(description=_GET_SECTION_DESCRIPTION, **auth_kwargs)(
        get_vault_entity_section,
    )
    _ = mcp.tool(description=_CREATE_DESCRIPTION, **auth_kwargs)(create_vault_entity)
    _ = mcp.tool(description=update_description, **auth_kwargs)(update_vault_entity)
