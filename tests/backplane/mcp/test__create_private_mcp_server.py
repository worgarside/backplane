"""Tests for the private MCP server entrypoint."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test__create_private_mcp_server__notifies_home_assistant_on_startup(
    mocker: MockerFixture,
) -> None:
    """The private MCP entrypoint enables Home Assistant startup notifications."""
    mock_create = mocker.patch("backplane.mcp.__main__.create_mcp_server")
    mock_server = mocker.Mock()
    mock_create.return_value = mock_server

    from backplane.mcp.__main__ import create_private_mcp_server  # noqa: PLC0415

    server = create_private_mcp_server()

    mock_create.assert_called_once_with(notify_home_assistant=True)
    assert server is mock_server


def test__main__starts_private_mcp_server(mocker: MockerFixture) -> None:
    """The private entrypoint main function runs the SSE MCP server."""
    run_target = object()
    mock_server = mocker.Mock()
    mock_server.run_async.return_value = run_target
    mocker.patch(
        "backplane.mcp.__main__.create_private_mcp_server",
        return_value=mock_server,
    )
    mock_uvloop = mocker.patch("backplane.mcp.__main__.uvloop.run")

    from backplane.mcp.__main__ import main  # noqa: PLC0415

    main()

    mock_server.run_async.assert_called_once_with(
        transport="sse",
        host="0.0.0.0",
        port=8000,
    )
    mock_uvloop.assert_called_once_with(run_target)
