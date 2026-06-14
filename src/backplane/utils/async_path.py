"""Pydantic-compatible async path type."""

from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING, override

import anyio
from pydantic_core import CoreSchema, core_schema

if TYPE_CHECKING:
    from os import PathLike

    from pydantic import GetCoreSchemaHandler


class AsyncPath(anyio.Path):
    """Pydantic-compatible ``anyio.Path`` for models and tool responses."""

    @classmethod
    def __get_pydantic_core_schema__(  # noqa: PLW3201
        cls,
        source_type: object,
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Register Pydantic validation and serialization for ``AsyncPath``.

        Accepts ``AsyncPath``, ``anyio.Path``, ``pathlib.Path``, or vault-relative
        path strings. Serializes to a posix string for JSON and ``model_dump()``.

        Args:
            source_type: Annotated or generic source type Pydantic is resolving.
            handler: Callback to delegate schema generation for nested types.

        Returns:
            Core schema validating path-like inputs and dumping posix strings.
        """

        def validate(value: object) -> AsyncPath:
            if isinstance(value, cls):
                return value

            if isinstance(value, anyio.Path):
                return cls(value.as_posix())

            if isinstance(value, str | pathlib.Path):
                return cls(value)

            msg = f"Expected path, got {type(value)!r}"
            raise TypeError(msg)

        def serialize_path(path: AsyncPath) -> str:
            return path.as_posix()

        from_str = core_schema.no_info_after_validator_function(
            validate,
            core_schema.str_schema(),
        )

        return core_schema.json_or_python_schema(
            json_schema=from_str,
            python_schema=core_schema.union_schema([
                core_schema.is_instance_schema(cls),
                from_str,
                core_schema.no_info_plain_validator_function(validate),
            ]),
            serialization=core_schema.plain_serializer_function_ser_schema(
                serialize_path,
                return_schema=core_schema.str_schema(),
            ),
        )

    @override
    def __truediv__(self, other: str | PathLike[str]) -> AsyncPath:
        return type(self)(self._path / other)

    @override
    def __rtruediv__(self, other: str | PathLike[str]) -> AsyncPath:
        return type(self)(other) / self
