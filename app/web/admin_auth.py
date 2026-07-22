"""Short-lived signed-cookie authentication for the founder-only post editor."""

from __future__ import annotations

import hashlib
import hmac
import time

from fastapi import Request
from starlette.responses import Response

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
