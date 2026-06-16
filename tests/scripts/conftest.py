"""Ensure repo-root ``scripts`` imports resolve ahead of this test directory."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_tests_scripts_dir = Path(__file__).resolve().parent

sys.path[:] = [path for path in sys.path if Path(path).resolve() != _tests_scripts_dir]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
