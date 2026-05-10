"""API routes for Backplane."""

from __future__ import annotations

from .obsidian.route import router as obsidian_router

__all__ = ["obsidian_router"]
