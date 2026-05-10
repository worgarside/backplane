"""FastAPI application entrypoint for Backplane."""

from __future__ import annotations

from typing import Final

from fastapi import FastAPI

from backplane import __version__
from backplane.api.routes import obsidian_router

app = FastAPI(title="Backplane", version=__version__)
app.include_router(obsidian_router)


@app.get("/health/check", tags=["health"])
async def health_check() -> dict[str, str]:
    """Return a simple health response for container orchestration."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    __host: Final = "0.0.0.0"  # noqa: S104
    __port: Final = 8000
    uvicorn.run(app, host=__host, port=__port)
