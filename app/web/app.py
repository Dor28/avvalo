"""FastAPI app factory for the anonymous web channel."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app.config import Settings
from app.obs.events import log_error
from app.web.abuse import (
    MAX_REQUEST_BODY_BYTES,
    EphemeralRequestBodyLimitMiddleware,
    configure_ephemeral_multipart,
)
from app.web.routes import router


def create_app(
    *,
    settings: Settings | None = None,
    session_factory: Any | None = None,
    debug: bool = False,
) -> FastAPI:
    """Create the server-rendered Avvalo web app."""

    web_app = FastAPI(
        title="Avvalo",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        debug=debug,
    )
    web_app.state.settings = settings
    web_app.state.session_factory = session_factory
    configure_ephemeral_multipart()
    web_app.router.routes.extend(router.routes)
    web_app.add_middleware(
        EphemeralRequestBodyLimitMiddleware,
        max_body_bytes=MAX_REQUEST_BODY_BYTES,
    )
    web_app.middleware("http")(_prevent_post_caching)
    web_app.add_exception_handler(Exception, _handle_unexpected_error)

    static_dir = Path(__file__).with_name("static")
    if static_dir.exists():
        web_app.mount("/static", StaticFiles(directory=static_dir), name="static")

    return web_app


async def _prevent_post_caching(request: Request, call_next):
    """Keep submitted content and check responses out of shared/browser caches."""

    response = await call_next(request)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    return response


async def _handle_unexpected_error(request: Request, exc: Exception) -> PlainTextResponse:
    """Catch-all for exceptions that escape a route without going through run_check().

    FastAPI's own HTTPException/RequestValidationError handlers still take
    priority for those specific types — this only ever sees genuinely
    unexpected failures.
    """

    log_error(stage="web", error_type=exc.__class__.__name__)
    return PlainTextResponse(
        "Internal Server Error",
        status_code=500,
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )


app = create_app()
