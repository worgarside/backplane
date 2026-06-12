"""Shared fixtures for vault entity MCP tests."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("entity_templates")
