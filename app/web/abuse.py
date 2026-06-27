"""Web-channel abuse controls: upload caps and Turnstile verification."""

from __future__ import annotations

import asyncio
import json
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import HTTPException, UploadFile
from starlette.requests import Request

from app.config import Settings

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


async def read_limited_upload(upload: UploadFile | None) -> bytes | None:
    """Read an optional upload while enforcing the v1 size cap."""

    if upload is None or not upload.filename:
        return None

    content = await upload.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image upload is too large.")
    return content or None


async def require_turnstile_for_image(
    *,
    image_bytes: bytes | None,
    token: str | None,
    request: Request,
    settings: Settings,
) -> None:
    """Reject image checks unless Turnstile is configured and solved."""

    if not image_bytes:
        return

    secret = settings.turnstile_secret
    if secret is None:
        raise HTTPException(status_code=400, detail="Image upload is not enabled here.")

    ok = await verify_turnstile(
        token=token,
        secret=secret.get_secret_value(),
        remote_ip=request.client.host if request.client else None,
    )
    if not ok:
        raise HTTPException(status_code=400, detail="Image upload verification failed.")


async def verify_turnstile(*, token: str | None, secret: str, remote_ip: str | None) -> bool:
    """Verify a Cloudflare Turnstile token."""

    if not token:
        return False
    return await asyncio.to_thread(_verify_turnstile_sync, token, secret, remote_ip)


def _verify_turnstile_sync(token: str, secret: str, remote_ip: str | None) -> bool:
    body = {"secret": secret, "response": token}
    if remote_ip:
        body["remoteip"] = remote_ip

    data = urlencode(body).encode("utf-8")
    request = UrlRequest(
        TURNSTILE_VERIFY_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except OSError:
        return False
    return bool(payload.get("success"))
