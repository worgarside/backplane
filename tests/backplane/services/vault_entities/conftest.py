"""Shared fixtures for vault entity service tests."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("entity_templates")
