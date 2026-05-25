"""Tests for task metadata agent run logging."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from backplane.services.tasks import _log_metadata_agent_run

if TYPE_CHECKING:
    from pydantic_ai import AgentRunResult
    from pytest_mock import MockerFixture

    from backplane.services.tasks import TaskMetadata

EXPECTED_INFO_CALLS = 3


@dataclass(frozen=True, slots=True)
class FakeUsage:
    """Agent usage values consumed by the logger."""

    requests: int = 1
    input_tokens: int = 2
    output_tokens: int = 3
    total_tokens: int = 5
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


@dataclass(frozen=True, slots=True)
class FakeCost:
    """Agent cost values consumed by the logger."""

    input_price: str = "0.01"
    output_price: str = "0.02"
    total_price: str = "0.03"


class FakeResponse:
    """Agent response object consumed by the logger."""

    model_name: str = "test-model"

    @staticmethod
    def cost() -> FakeCost:
        """Return deterministic cost data."""
        return FakeCost()


class RaisingFakeResponse:
    """Agent response whose cost lookup fails."""

    model_name: str = "test-model"

    @staticmethod
    def cost() -> FakeCost:
        """Raise to exercise best-effort cost logging.

        Raises:
            RuntimeError: Always raised to simulate unavailable cost data.
        """
        msg = "cost unavailable"
        raise RuntimeError(msg)


@dataclass(frozen=True, slots=True)
class FakeRunResult:
    """Agent run result shape consumed by the logger."""

    usage: FakeUsage
    response: FakeResponse | RaisingFakeResponse


def test__log_metadata_agent_run_logs_usage_cache_tokens_and_cost(
    mocker: MockerFixture,
) -> None:
    """Usage, cache tokens, and cost are logged when available."""
    mock_info = mocker.patch("backplane.services.tasks.logger.info")
    mocker.patch("backplane.services.tasks.logger.warning")
    result = cast(
        "AgentRunResult[TaskMetadata]",
        FakeRunResult(
            usage=FakeUsage(cache_read_tokens=7, cache_write_tokens=11),
            response=FakeResponse(),
        ),
    )

    _log_metadata_agent_run(result)

    assert mock_info.call_count == EXPECTED_INFO_CALLS


def test__log_metadata_agent_run_warns_when_cost_unavailable(
    mocker: MockerFixture,
) -> None:
    """Cost lookup failures are logged without raising."""
    mock_warning = mocker.patch("backplane.services.tasks.logger.warning")
    result = cast(
        "AgentRunResult[TaskMetadata]",
        FakeRunResult(
            usage=FakeUsage(),
            response=RaisingFakeResponse(),
        ),
    )

    _log_metadata_agent_run(result)

    mock_warning.assert_called_once()
