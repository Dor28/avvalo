"""Admin gate for the founder-only editors: signed-cookie auth and the shared guards.

The three admin routers (posts, rules, cards) enter through the same checks, so
they live here once rather than once per router.
"""

from __future__ import annotations

import hashlib
import hmac
import time

from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.responses import RedirectResponse, Response

from app.config import Settings

ADMIN_COOKIE_NAME = "avvalo_admin_session"
ADMIN_SESSION_SECONDS = 60 * 60 * 12


def access_key_matches(candidate: str, settings: Settings) -> bool:
    """Compare the submitted key in constant time; disabled means no match."""

    configured = settings.admin_access_key
    if configured is None:
        return False
    return hmac.compare_digest(candidate, configured.get_secret_value())


def is_admin_authenticated(request: Request, settings: Settings) -> bool:
    """Validate the signed expiry carried by the dedicated admin cookie."""

    value = request.cookies.get(ADMIN_COOKIE_NAME)
    if not value or "." not in value:
        return False
    expires_text, signature = value.rsplit(".", 1)
    if not expires_text.isdigit() or int(expires_text) <= int(time.time()):
        return False
    expected = _signature(expires_text, settings.web_session_secret.get_secret_value())
    return hmac.compare_digest(signature, expected)


def set_admin_cookie(response: Response, settings: Settings, *, secure: bool) -> None:
    """Create a 12-hour HttpOnly session scoped to founder routes."""

    expires_text = str(int(time.time()) + ADMIN_SESSION_SECONDS)
    signature = _signature(expires_text, settings.web_session_secret.get_secret_value())
    response.set_cookie(
        ADMIN_COOKIE_NAME,
        f"{expires_text}.{signature}",
        max_age=ADMIN_SESSION_SECONDS,
        httponly=True,
        secure=secure,
        samesite="strict",
        path="/admin",
    )


def clear_admin_cookie(response: Response) -> None:
    """Invalidate the dedicated admin session cookie."""

    response.delete_cookie(ADMIN_COOKIE_NAME, path="/admin", httponly=True, samesite="strict")


def _signature(expires_text: str, secret: str) -> str:
    return hmac.new(secret.encode(), f"admin:{expires_text}".encode(), hashlib.sha256).hexdigest()


def admin_settings_or_404(request: Request) -> Settings:
    """Return settings only when the admin surface is configured and enabled.

    A blank or absent ``ADMIN_ACCESS_KEY`` disables /admin entirely, and it does
    so as a 404 rather than a 403 so the surface is not advertised.
    """

    settings = getattr(request.app.state, "settings", None)
    if settings is None or settings.admin_access_key is None:
        raise HTTPException(status_code=404)
    if not settings.admin_access_key.get_secret_value():
        raise HTTPException(status_code=404)
    return settings


def admin_no_store(response: Response) -> Response:
    """Keep an admin response out of every cache, shared or private."""

    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response


def require_admin(
    request: Request, settings: Settings, language: str
) -> RedirectResponse | None:
    """Return ``None`` when authenticated, else the redirect to the login page."""

    if is_admin_authenticated(request, settings):
        return None
    return admin_no_store(
        RedirectResponse(f"/admin/login?language={language}", status_code=303)
    )


def admin_session_factory(
    request: Request, *, detail: str
) -> async_sessionmaker[AsyncSession]:
    """Return the configured session factory, or 503 with the caller's wording."""

    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory is None:
        raise HTTPException(status_code=503, detail=detail)
    return session_factory
