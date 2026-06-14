"""Vault entity notes for Domains, People, Projects, and Resources."""

from __future__ import annotations

import datetime as dt
import pathlib
from typing import TYPE_CHECKING, Final, Literal, TypedDict, final, overload

from loguru import logger

from backplane.utils import (
    VAULT_PATHS,
    AsyncPath,
    MarkdownDocument,
    append_board_card,
    atomic_write_text,
    build_vault_note_metadata,
    exc,
    note_filename,
    resolve_under_root,
    safe_slug,
    substitute_vault_entity_template,
)
from backplane.utils.enums import VaultEntityKind
from backplane.utils.settings import SETTINGS

if TYPE_CHECKING:
    from backplane.utils.helpers.obsidian import VaultNoteMetadata
    from backplane.utils.markdown import MarkdownSection

_ENTITY_TEMPLATES: Final = {
    VaultEntityKind.DOMAIN: VAULT_PATHS.templates_dir / "Domain.md",
    VaultEntityKind.PERSON: VAULT_PATHS.templates_dir / "Person.md",
    VaultEntityKind.PROJECT: VAULT_PATHS.templates_dir / "Project.md",
    VaultEntityKind.RESOURCE: VAULT_PATHS.templates_dir / "Resource.md",
}

UpdateMode = Literal["append", "prepend", "replace"]


class VaultEntitySection(TypedDict):
    """A section heading within a vault entity note."""

    heading: str
    path: list[str]
    level: int


def note_title_from_markdown(text: str) -> str | None:
    """Return the first level-1 heading text, skipping YAML frontmatter."""
    in_frontmatter = False
    frontmatter_closed = False
    for line in text.splitlines():
        stripped = line.strip()

        if not frontmatter_closed and stripped == "---":
            in_frontmatter = not in_frontmatter
            if not in_frontmatter:
                frontmatter_closed = True
            continue

        if in_frontmatter:
            continue

        if line.startswith("# ") and not line.startswith("## "):
            return line.removeprefix("# ").strip()

    return None


def _section_entries(
    sections: list[MarkdownSection],
    *,
    parent_path: tuple[str, ...] = (),
) -> list[VaultEntitySection]:
    """Return flat section metadata in document order."""
    entries: list[VaultEntitySection] = []
    for section in sections:
        section_path = (*parent_path, section.heading)
        entries.append(
            {
                "heading": section.heading,
                "path": list(section_path),
                "level": section.level,
            },
        )
        entries.extend(_section_entries(section.sections, parent_path=section_path))
    return entries


def _vault_relative_path(path: AsyncPath) -> pathlib.PurePath:
    """Return a vault-relative pure path for ``MarkdownDocument`` construction."""
    root_resolved = pathlib.Path(SETTINGS.obsidian_vault_path.as_posix()).resolve()
    path_resolved = pathlib.Path(path.as_posix())
    return pathlib.PurePath(path_resolved.relative_to(root_resolved).as_posix())


@final
class VaultEntityService:
    """Service for listing, reading, creating, and updating vault entity notes."""

    @staticmethod
    def template_path_for(kind: VaultEntityKind) -> AsyncPath:
        """Return the vault-relative template path for an entity kind."""
        return _ENTITY_TEMPLATES[kind]

    @staticmethod
    async def list_entities(kind: VaultEntityKind) -> list[str]:
        """List display names of entity notes in the vault subdirectory.

        Returns:
            Sorted unique note titles from H1 headings, or an empty list if the
            directory is missing.
        """
        dir_path = await resolve_under_root(kind.vault_dir)
        if not await dir_path.is_dir():
            return []

        names: list[str] = []
        async for entry in dir_path.iterdir():
            if entry.suffix != ".md" or not await entry.is_file():
                continue

            text = await entry.read_text(encoding="utf-8")
            if title := note_title_from_markdown(text):
                names.append(title)

        return sorted(
            {name.casefold(): name for name in names}.values(),
            key=str.casefold,
        )

    @staticmethod
    @overload
    async def resolve_entity_path(
        kind: VaultEntityKind,
        name: str,
        *,
        must_exist: Literal[True],
    ) -> AsyncPath: ...

    @overload
    @staticmethod
    async def resolve_entity_path(
        kind: VaultEntityKind,
        name: str,
        *,
        must_exist: Literal[False] = False,
    ) -> AsyncPath | None: ...

    @staticmethod
    async def resolve_entity_path(
        kind: VaultEntityKind,
        name: str,
        *,
        must_exist: bool = False,
    ) -> AsyncPath | None:
        """Resolve an entity display name to its on-disk path.

        Args:
            kind: Entity kind determining the search directory.
            name: Human-readable entity name.
            must_exist: Raise ``NotFoundError`` instead of returning ``None`` when
                no matching entity note exists.

        Returns:
            Absolute path to the note, or ``None`` when no match exists.

        Raises:
            NotFoundError: If ``must_exist`` is true and the note does not exist.
        """
        directory = await resolve_under_root(kind.vault_dir)
        readable_path = directory / f"{note_filename(name)}.md"
        if await readable_path.exists():
            return AsyncPath(readable_path.as_posix())

        slug_path = directory / f"{safe_slug(name)}.md"
        if await slug_path.exists():
            return AsyncPath(slug_path.as_posix())

        if await directory.is_dir():
            target = name.casefold()
            async for entry in directory.iterdir():
                if entry.suffix != ".md" or not await entry.is_file():
                    continue

                text = await entry.read_text(encoding="utf-8")
                title = note_title_from_markdown(text)
                if title is not None and title.casefold() == target:
                    return AsyncPath(entry.as_posix())

        if must_exist:
            msg = f"{kind.value.title()} {name!r} not found."
            raise exc.NotFoundError(message=msg)

        return None

    @staticmethod
    async def render_entity_from_template(kind: VaultEntityKind, name: str) -> str:
        """Load and expand the configured Obsidian template for an entity kind.

        Args:
            kind: Entity kind determining which template file to load.
            name: Display title substituted into the template.

        Returns:
            Rendered markdown ready to write as a new entity note.

        Raises:
            UserError: If the template file is missing.
        """
        template_rel = VaultEntityService.template_path_for(kind)
        template_path = SETTINGS.obsidian_vault_path / template_rel
        try:
            template_text = await template_path.read_text(encoding="utf-8")
        except FileNotFoundError as err:
            msg = f"Template not found: {template_rel}"
            raise exc.UserError(message=msg) from err

        return substitute_vault_entity_template(template_text, title=name)

    @staticmethod
    async def get_entity(kind: VaultEntityKind, name: str) -> str:
        """Read an entity note as rendered markdown.

        Returns:
            The entity note rendered as markdown.
        """
        path = await VaultEntityService.resolve_entity_path(kind, name, must_exist=True)

        async with MarkdownDocument(
            vault_path=_vault_relative_path(path),
            read_only=True,
        ) as document:
            return document.render()

    @staticmethod
    async def list_entity_sections(
        kind: VaultEntityKind,
        name: str,
    ) -> list[VaultEntitySection]:
        """List sections in an entity note.

        Args:
            kind: Entity kind determining the search directory.
            name: Human-readable entity name.

        Returns:
            Section metadata in document order. Paths are relative to the note's
            level-1 title heading.
        """
        path = await VaultEntityService.resolve_entity_path(kind, name, must_exist=True)

        async with MarkdownDocument(
            vault_path=_vault_relative_path(path),
            read_only=True,
        ) as document:
            if len(document.body) != 1 or document.body[0].level != 1:
                return _section_entries(document.body)

            root_section = document.body[0]
            return _section_entries(root_section.sections)

    @staticmethod
    async def get_entity_section(
        kind: VaultEntityKind,
        name: str,
        *,
        section: str,
    ) -> str:
        """Read a section of an entity note as rendered markdown.

        Args:
            kind: Entity kind determining the search directory.
            name: Human-readable entity name.
            section: Top-level section heading to read (e.g. ``Overview``).

        Returns:
            The requested section rendered as markdown.

        Raises:
            InformationRequiredError: If the section is missing.
        """
        path = await VaultEntityService.resolve_entity_path(kind, name, must_exist=True)

        async with MarkdownDocument(
            vault_path=_vault_relative_path(path),
            read_only=True,
        ) as document:
            try:
                target_section = document.get_section((name, section))
            except exc.SectionNotFoundError as err:
                raise exc.InformationRequiredError(
                    message=f"{err} Retry with an existing section.",
                    detail=err.detail,
                ) from err

            return target_section.render()

    @staticmethod
    async def create_entity(
        kind: VaultEntityKind,
        name: str,
        *,
        provenance_note: str | None = None,
    ) -> VaultNoteMetadata:
        """Create a new entity note from the vault template.

        Args:
            kind: Entity kind determining directory and template.
            name: Human-readable entity name used as the note title.
            provenance_note: Optional markdown appended to the ``Notes`` section after
                creation (used when task intake creates linked stubs).

        Returns:
            Structured metadata for the created note.

        Raises:
            ConflictError: If a note with the same name already exists.
        """
        if await VaultEntityService.resolve_entity_path(kind, name) is not None:
            msg = f"{kind.value.title()} {name!r} already exists."
            raise exc.ConflictError(message=msg)

        rel_path = kind.vault_dir / f"{note_filename(name)}.md"

        content = await VaultEntityService.render_entity_from_template(kind, name)
        target = await resolve_under_root(rel_path)

        await target.parent.mkdir(parents=True, exist_ok=True)
        await atomic_write_text(target, content)

        if kind == VaultEntityKind.PROJECT:
            board_path = await resolve_under_root(VAULT_PATHS.project_board_path)
            await append_board_card(board_path, rel_path)

        if provenance_note:
            async with MarkdownDocument(vault_path=rel_path, read_only=False) as document:
                section = document.get_section(
                    (name, "Notes"),
                    create_if_not_exists=True,
                )
                section.append_content(provenance_note)

        logger.info("Created vault entity note: {}", rel_path)
        return build_vault_note_metadata(
            kind=kind,
            title=name,
            path=rel_path,
        )

    @staticmethod
    async def update_entity(
        kind: VaultEntityKind,
        name: str,
        *,
        section: str,
        content: str,
        mode: UpdateMode = "append",
        create_section_if_not_exists: bool = False,
    ) -> str:
        """Update a section of an entity note.

        Args:
            kind: Entity kind determining the search directory.
            name: Human-readable entity name.
            section: Top-level section heading to update (e.g. ``Overview``).
            content: Markdown content to combine with the section.
            mode: How to combine ``content`` with existing section text.
            create_section_if_not_exists: Create the section when missing.

        Returns:
            The updated section rendered as markdown.

        Raises:
            InformationRequiredError: If the section is missing and creation is
                disabled.
        """
        path = await VaultEntityService.resolve_entity_path(kind, name, must_exist=True)

        now = dt.datetime.now(tz=SETTINGS.local_timezone).replace(microsecond=0)

        async with MarkdownDocument(
            vault_path=_vault_relative_path(path),
            read_only=False,
        ) as document:
            try:
                target_section = document.get_section(
                    (name, section),
                    create_if_not_exists=create_section_if_not_exists,
                )
            except exc.SectionNotFoundError as err:
                raise exc.InformationRequiredError(
                    message=(
                        f"{err} Retry with an existing section, or set "
                        "`create_section_if_not_exists=true` to create it."
                    ),
                    detail=err.detail,
                ) from err

            if not target_section.content or mode == "replace":
                target_section.replace_content(content)
            elif mode == "append":
                target_section.append_content(content)
            elif mode == "prepend":
                target_section.prepend_content(content)

            document.frontmatter["updated"] = now.isoformat(timespec="seconds")

        return target_section.render()
