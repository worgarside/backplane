"""CLI entrypoint for regenerating the MCP catalog section in README.md."""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
README_PATH = REPO_ROOT / "README.md"
FIXTURE_VAULT = REPO_ROOT / "scripts" / "fixtures" / "readme-vault"


def main() -> int:
    """Update README.md and return a pre-commit-friendly exit code.

    Returns:
        1 when README.md changed, 0 when already up to date.
    """
    os.environ["OBSIDIAN_VAULT_PATH"] = str(FIXTURE_VAULT)
    if "LOCAL_TIMEZONE" not in os.environ:
        os.environ["LOCAL_TIMEZONE"] = "UTC"

    from backplane.docs.mcp_catalog import refresh_readme_catalog  # noqa: PLC0415

    changed = refresh_readme_catalog(README_PATH)
    return 1 if changed else 0


if __name__ == "__main__":
    sys.exit(main())
