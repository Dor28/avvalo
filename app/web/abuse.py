"""Web-channel abuse controls: upload caps and Turnstile verification."""

from __future__ import annotations

import asyncio
import json
from ipaddress import ip_address
from urllib.parse import urlencode, urlsplit
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import HTTPException, UploadFile
from starlette.formparsers import MultiPartParser
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import Settings
from app.engine.types import MAX_IMAGE_BYTES
from app.privacy.user_key import derive_user_key

MAX_UPLOAD_BYTES = MAX_IMAGE_BYTES
# Includes multipart framing and the small text fields submitted alongside an
# image.  Keeping this below the multipart spool threshold ensures submitted
# content is rejected from memory before Starlette can roll it onto disk.
MAX_REQUEST_BODY_BYTES = 12 * 1024 * 1024
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


class _RequestBodyTooLarge(Exception):
    """Internal control flow for a streaming request-body rejection."""


class EphemeralRequestBodyLimitMiddleware:
    """Cap request bodies before multipart uploads can spill to a temp file."""

    def __init__(self, app: ASGIApp, *, max_body_bytes: int = MAX_REQUEST_BODY_BYTES) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") not in {"POST", "PUT", "PATCH"}:
            await self.app(scope, receive, send)
            return

        content_length = _content_length(scope)
        if content_length is not None and content_length > self.max_body_bytes:
            await _send_body_too_large(scope, receive, send)
            return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_body_bytes:
                    raise _RequestBodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _RequestBodyTooLarge:
            await _send_body_too_large(scope, receive, send)


def configure_ephemeral_multipart() -> None:
    """Keep every accepted multipart body in memory for its ephemeral lifetime."""

    MultiPartParser.spool_max_size = MAX_REQUEST_BODY_BYTES + 1


def _content_length(scope: Scope) -> int | None:
    for name, value in scope.get("headers", []):
        if name.lower() != b"content-length":
            continue
        try:
            return int(value)
        except ValueError:
            return None
    return None


async def _send_body_too_large(scope: Scope, receive: Receive, send: Send) -> None:
    response = Response(
        status_code=413,
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )
    await response(scope, receive, send)


def require_same_origin(request: Request) -> None:
    """Reject browser POSTs initiated by another origin.

    Requests without browser origin metadata remain available to non-browser
    clients and are still subject to the normal per-IP and per-session limits.
    """

    fetch_site = request.headers.get("sec-fetch-site", "").strip().casefold()
    if fetch_site == "cross-site":
        raise HTTPException(status_code=403, detail="Cross-site request rejected.")

    origin = request.headers.get("origin")
    if not origin:
        return

    try:
        parsed = urlsplit(origin)
        origin_port = parsed.port or _default_port(parsed.scheme)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Invalid request origin.") from exc

    expected_scheme = _request_scheme(request)
    expected_host = (request.url.hostname or "").rstrip(".").casefold()
    expected_port = request.url.port or _default_port(expected_scheme)
    origin_host = (parsed.hostname or "").rstrip(".").casefold()
    if (
        parsed.scheme.casefold() not in {"http", "https"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or (parsed.scheme.casefold(), origin_host, origin_port)
        != (expected_scheme, expected_host, expected_port)
    ):
        raise HTTPException(status_code=403, detail="Cross-site request rejected.")


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


def pseudonymous_ip_key(request: Request, *, secret: str) -> str | None:
    """Return a privacy-safe daily-limit key for the request's client IP."""

    client_ip = client_ip_from_request(request)
    if client_ip is None:
        return None
    return derive_user_key(f"web-ip:{client_ip}", secret=secret)


def client_ip_from_request(request: Request) -> str | None:
    """Resolve the rate-limit peer from trusted proxy headers or the socket peer."""

    peer = request.client.host if request.client else None
    if _is_trusted_proxy_peer(peer):
        real_ip = _normalized_ip(request.headers.get("x-real-ip"))
        if real_ip is not None:
            return real_ip

        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            for candidate in reversed([part.strip() for part in forwarded_for.split(",")]):
                normalized = _normalized_ip(candidate)
                if normalized is not None:
                    return normalized

    if peer is None:
        return None
    return _normalized_ip(peer) or peer.casefold()


def _is_trusted_proxy_peer(peer: str | None) -> bool:
    if peer is None:
        return False
    try:
        address = ip_address(peer)
    except ValueError:
        return False
    return address.is_loopback or address.is_private or address.is_link_local


def _normalized_ip(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(ip_address(value.strip()))
    except ValueError:
        return None


def _request_scheme(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip()
    if forwarded.casefold() in {"http", "https"}:
        return forwarded.casefold()
    return request.url.scheme.casefold()


def _default_port(scheme: str) -> int | None:
    return {"http": 80, "https": 443}.get(scheme.casefold())


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
