"""Tests for shared YAML configuration."""

from __future__ import annotations

import io
from typing import cast

from backplane.utils import enums
from backplane.utils.yaml import YAML_LOADER, FrontmatterValue


def _dump_yaml(data: object) -> str:
    """Dump data through the shared YAML loader."""
    buffer = io.StringIO()
    YAML_LOADER.dump(data, buffer)  # pyright: ignore[reportUnknownMemberType]
    return buffer.getvalue()


def test__yaml_loader__serializes_str_enum_as_scalar() -> None:
    """String enums are emitted as plain YAML scalar values."""
    text = _dump_yaml({"priority": enums.Priority.MEDIUM})

    assert "priority: medium\n" in text
    assert "Priority.MEDIUM" not in text
    assert "!!python" not in text


def test__yaml_loader__loads_serialized_str_enum_as_string() -> None:
    """Serialized string enums round-trip back as regular strings."""
    text = _dump_yaml({"priority": enums.Priority.MEDIUM})

    loaded = cast(
        "dict[str, FrontmatterValue]",
        YAML_LOADER.load(text),  # pyright: ignore[reportUnknownMemberType]
    )

    assert loaded["priority"] == "medium"
