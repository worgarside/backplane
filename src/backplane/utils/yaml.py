"""Shared YAML configuration and types."""

from __future__ import annotations

import datetime as dt
import enum
from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol, cast

from ruamel.yaml import YAML
from ruamel.yaml.representer import RoundTripRepresenter

if TYPE_CHECKING:
    from ruamel.yaml.nodes import ScalarNode


class _ScalarRepresenter(Protocol):
    """Subset of ruamel's representer API used by custom serializers."""

    def represent_scalar(
        self,
        tag: str,
        value: str,
        style: object | None = None,
        anchor: object | None = None,
    ) -> ScalarNode:
        """Represent a scalar YAML node."""
        ...


type _StrEnumRepresenter = Callable[[_ScalarRepresenter, enum.StrEnum], ScalarNode]
type _AddMultiRepresenter = Callable[[type[enum.StrEnum], _StrEnumRepresenter], None]

# YAML 1.2 produces these scalar Python types under ``YAML(typ="rt")``. Order matters
# for Pydantic union resolution: ``bool`` must precede ``int`` (since ``True`` is
# also an ``int``) and ``datetime`` must precede ``date`` (since ``datetime``
# subclasses ``date``). ruamel.yaml's tagged subclasses (``DoubleQuotedScalarString``,
# ``ScalarBoolean``, ``TimeStamp``, ...) all inherit from these natives, so the
# loaded values satisfy this union without coercion.
type FrontmatterScalar = bool | int | float | str | dt.datetime | dt.date | None

# Frontmatter values are arbitrary YAML scalars or nested containers.
type FrontmatterValue = (
    FrontmatterScalar | list[FrontmatterValue] | dict[str, FrontmatterValue]
)

YAML_LOADER = YAML(typ="rt")
YAML_LOADER.explicit_start = True
YAML_LOADER.preserve_quotes = True
YAML_LOADER.indent(mapping=2, sequence=4, offset=2)  # pyright: ignore[reportAny]
YAML_LOADER.width = 4096


def _represent_str_enum(
    representer: _ScalarRepresenter,
    data: enum.StrEnum,
) -> ScalarNode:
    """Serialize string enums as their scalar values.

    Returns:
        YAML scalar node containing the enum's string value.
    """
    return representer.represent_scalar("tag:yaml.org,2002:str", data.value)


_add_multi_representer = cast(
    "_AddMultiRepresenter",
    RoundTripRepresenter.add_multi_representer,
)
_add_multi_representer(
    enum.StrEnum,
    _represent_str_enum,
)
