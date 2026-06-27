"""FastAPI app factory for the anonymous web channel."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import Settings
from app.web.routes import router


def create_app(
    *,
    settings: Settings | None = None,
    session_factory: Any | None = None,
) -> FastAPI:
    """Create the server-rendered Avvalo web app."""

    web_app = FastAPI(title="Avvalo", docs_url=None, redoc_url=None)
    web_app.state.settings = settings
    web_app.state.session_factory = session_factory
    web_app.router.routes.extend(router.routes)

    static_dir = Path(__file__).with_name("static")
    if static_dir.exists():
        web_app.mount("/static", StaticFiles(directory=static_dir), name="static")

    return web_app


app = create_app()
