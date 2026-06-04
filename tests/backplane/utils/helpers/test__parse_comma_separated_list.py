"""Tests for Pydantic comma-separated list parsing."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel

from backplane.utils.helpers.pydantic_validators import ParseCommaSeparatedList


class _CommaSeparatedListModel(BaseModel):
    values: Annotated[list[str], ParseCommaSeparatedList]


def test__parse_comma_separated_list__splits_trimmed_parts() -> None:
    """Comma-separated strings become trimmed, non-empty list items."""
    model = _CommaSeparatedListModel.model_validate(
        {"values": " alpha , beta , , gamma "},
    )

    assert model.values == ["alpha", "beta", "gamma"]


def test__parse_comma_separated_list__passes_through_lists() -> None:
    """Non-string values are left unchanged."""
    model = _CommaSeparatedListModel.model_validate(
        {"values": ["one", "two"]},
    )

    assert model.values == ["one", "two"]
