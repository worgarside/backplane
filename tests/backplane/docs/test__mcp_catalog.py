"""Tests for MCP README catalog generation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from backplane.docs.mcp_catalog import (
    README_CATALOG_END,
    README_CATALOG_START,
    McpCatalog,
    McpParameterRow,
    McpResourceDoc,
    McpResourceTemplateDoc,
    McpToolDoc,
    _schema_type_label,
    render_mcp_catalog_markdown,
    render_readme_catalog_section,
    update_readme_catalog,
)


def test__schema_type_label__formats_common_json_schema_shapes() -> None:
    """JSON schema helpers render concise markdown type labels."""
    assert _schema_type_label({"type": "string"}) == "`string`"
    assert (
        _schema_type_label({"type": "string", "format": "date"}) == "`date` (YYYY-MM-DD)"
    )
    assert _schema_type_label({"enum": ["append", "prepend", "replace"]}) == (
        "`append` \\| `prepend` \\| `replace`"
    )
    assert (
        _schema_type_label({"type": "array", "items": {"type": "string"}}) == "`string`[]"
    )
    assert (
        _schema_type_label({"anyOf": [{"type": "string"}, {"type": "null"}]})
        == "`string`?"
    )


def test__render_mcp_catalog_markdown__includes_tools_resources_and_templates() -> None:
    """Rendered markdown documents tools, resources, and templates."""
    catalog = McpCatalog(
        server_name="Backplane",
        server_version="0.0.0",
        instructions="Keep outputs concise.",
        tools=(
            McpToolDoc(
                name="create_task",
                description="Create a task.",
                parameters=(
                    McpParameterRow(
                        name="description",
                        type_label="`string`",
                        required=True,
                        default="—",
                        description="Task text.",
                    ),
                ),
            ),
        ),
        resources=(
            McpResourceDoc(
                name="Today's Daily Note",
                uri="obsidian://daily-note/today",
                description="Today's note.",
                mime_type="text/markdown",
            ),
        ),
        resource_templates=(
            McpResourceTemplateDoc(
                name="Daily Note by Date",
                uri_template="obsidian://daily-note/{date}",
                description="Note for a date.",
                mime_type="text/markdown",
                parameters=(
                    McpParameterRow(
                        name="date",
                        type_label="`date` (YYYY-MM-DD)",
                        required=True,
                        default="—",
                        description="ISO date.",
                    ),
                ),
            ),
        ),
    )

    markdown = render_mcp_catalog_markdown(catalog)

    assert "#### `create_task`" in markdown
    assert "| `description` | `string` | yes | — | Task text. |" in markdown
    assert "obsidian://daily-note/today" in markdown
    assert "obsidian://daily-note/{date}" in markdown


def test__update_readme_catalog__replaces_existing_marked_section(tmp_path: Path) -> None:
    """README updates replace only the marked MCP catalog section."""
    readme = tmp_path / "README.md"
    readme.write_text(
        f"# Example\n\n{README_CATALOG_START}\n"
        "## MCP tools and resources\n\n"
        "old content\n\n"
        f"{README_CATALOG_END}\n\n"
        "### Public MCP (ChatGPT)\n\n",
        encoding="utf-8",
    )
    catalog = McpCatalog(
        server_name="Backplane",
        server_version="1.2.3",
        instructions="New instructions.",
        tools=(),
        resources=(),
        resource_templates=(),
    )

    changed = update_readme_catalog(readme, catalog)

    assert changed is True
    text = readme.read_text(encoding="utf-8")
    assert "old content" not in text
    assert "New instructions." in text
    assert "### Public MCP (ChatGPT)" in text


def test__update_readme_catalog__is_noop_when_content_unchanged(tmp_path: Path) -> None:
    """README updates return false when the rendered section is unchanged."""
    catalog = McpCatalog(
        server_name="Backplane",
        server_version="1.2.3",
        instructions="Same instructions.",
        tools=(),
        resources=(),
        resource_templates=(),
    )
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Example\n\n" + render_readme_catalog_section(catalog),
        encoding="utf-8",
    )

    changed = update_readme_catalog(readme, catalog)

    assert changed is False


@pytest.mark.parametrize(
    ("schema", "expected"),
    [
        ({"type": "boolean", "default": False}, "`boolean`"),
        ({"type": "boolean", "default": True}, "`boolean`"),
    ],
)
def test__schema_type_label__boolean(schema: dict[str, object], expected: str) -> None:
    """Boolean schemas render as markdown code spans."""
    assert _schema_type_label(schema) == expected
