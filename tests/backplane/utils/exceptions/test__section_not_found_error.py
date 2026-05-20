"""Tests for Backplane exception types."""

from __future__ import annotations

from http import HTTPStatus

from backplane.utils import exc
from backplane.utils.exceptions import (
    BackplaneError,
    InformationRequiredError,
    NotFoundError,
    SectionNotFoundError,
    UserError,
)


def test__backplane_error_stores_message_and_serializes_detail() -> None:
    """Detail objects are converted to JSON-safe values on the exception."""
    err = BackplaneError(message="oops", detail={"key": "value"})

    assert str(err) == "oops"
    assert err.message == "oops"
    assert err.detail == {"key": "value"}


def test__section_not_found_error_exposes_context() -> None:
    """Section lookup failures retain the requested and available headings."""
    err = SectionNotFoundError("Ideas", parent="Thursday", siblings=["Tasks", "Notes"])

    assert err.section == "Ideas"
    assert err.parent == "Thursday"
    assert err.siblings == ["Tasks", "Notes"]
    assert "Ideas" in str(err)
    assert "Tasks" in str(err)
    assert isinstance(err, NotFoundError)
    assert err.STATUS_CODE is HTTPStatus.NOT_FOUND


def test__user_error_and_information_required_error_are_backplane_errors() -> None:
    """Actor-facing errors inherit from the shared base type."""
    user_err = UserError(message="bad input")
    info_err = InformationRequiredError(message="need more")

    assert isinstance(user_err, BackplaneError)
    assert isinstance(info_err, BackplaneError)


def test__utils_package_exports_exc_alias() -> None:
    """The public utils namespace exposes the exceptions module as ``exc``."""
    assert exc.SectionNotFoundError is SectionNotFoundError


def test__section_not_found_error_minimal_constructor() -> None:
    """Parent and siblings are optional for shallow section trees."""
    err = SectionNotFoundError("Backlog")

    assert err.parent is None
    assert err.siblings is None
    assert str(err) == "Section 'Backlog' not found."
    assert "None" not in str(err)
