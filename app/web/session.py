"""Anonymous signed-cookie session helpers for the web channel."""

from __future__ import annotations

import base64
import hashlib
import hmac
import uuid
from dataclasses import dataclass

from starlette.requests import Request
from starlette.responses import Response

from app.privacy.user_key import derive_user_key

COOKIE_NAME = "avvalo_web_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 90


@dataclass(frozen=True)
class WebSession:
    """Anonymous web session state safe to keep in a signed cookie."""

    user_key: str
    signed_id: str
    is_new: bool


def get_or_create_web_session(request: Request, *, secret: str) -> WebSession:
    """Return a stable pseudonymous key for this browser session."""

    signed_id = request.cookies.get(COOKIE_NAME)
    session_id = _unsign(signed_id, secret=secret) if signed_id else None
    is_new = session_id is None
    if session_id is None:
        session_id = uuid.uuid4().hex
        signed_id = _sign(session_id, secret=secret)

    return WebSession(
        user_key=derive_user_key(f"web:{session_id}", secret=secret),
        signed_id=signed_id,
        is_new=is_new,
    )


def set_web_session_cookie(
    response: Response, web_session: WebSession, *, secure: bool = False
) -> None:
    """Persist the anonymous signed session cookie.

    ``secure`` should be True in production (HTTPS) so the cookie is never sent
    over plaintext; it defaults False for local http development.
    """

    response.set_cookie(
        COOKIE_NAME,
        web_session.signed_id,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=secure,
        samesite="lax",
    )


def _sign(session_id: str, *, secret: str) -> str:
    payload = base64.urlsafe_b64encode(session_id.encode("utf-8")).decode("ascii").rstrip("=")
    signature = hmac.new(
        secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256
    ).hexdigest()
    return f"{payload}.{signature}"


def _unsign(value: str | None, *, secret: str) -> str | None:
    if not value or "." not in value:
        return None

    payload, signature = value.rsplit(".", 1)
    expected = hmac.new(
        secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None

    padding = "=" * (-len(payload) % 4)
    try:
        return base64.urlsafe_b64decode(f"{payload}{padding}").decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
