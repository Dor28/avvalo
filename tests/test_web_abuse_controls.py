"""Web-channel abuse controls: body caps, same-origin, Turnstile, peer resolution.

These are the guards that sit in front of the engine on the anonymous web
channel. Each is security- or privacy-relevant on its own:

- the body cap must reject an oversized upload *before* Starlette can spool
  submitted content onto disk, which would break the ephemerality invariant;
- ``require_same_origin`` is the CSRF guard for browser POSTs;
- ``client_ip_from_request`` decides the rate-limit identity, so trusting a
  proxy header from an untrusted peer would let a client forge its own key.
"""

import json
from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile
from starlette.requests import Request

from app.web.abuse import (
    MAX_REQUEST_BODY_BYTES,
    MAX_UPLOAD_BYTES,
    EphemeralRequestBodyLimitMiddleware,
    _verify_turnstile_sync,
    client_ip_from_request,
    pseudonymous_ip_key,
    read_limited_upload,
    require_same_origin,
    require_turnstile_for_image,
    verify_turnstile,
)


def _request(
    *,
    headers: dict[str, str] | None = None,
    client: tuple[str, int] | None = ("203.0.113.9", 5000),
    scheme: str = "https",
    host: str = "avvalo.uz",
    port: int | None = None,
) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    raw.append((b"host", host.encode() if port is None else f"{host}:{port}".encode()))
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": scheme,
            "path": "/check",
            "raw_path": b"/check",
            "query_string": b"",
            "root_path": "",
            "headers": raw,
            "client": client,
            "server": (host, port or (443 if scheme == "https" else 80)),
        }
    )


# ── request body cap ────────────────────────────────────────────────────────


class _Recorder:
    """Downstream ASGI app that drains the body and records what it saw."""

    def __init__(self) -> None:
        self.called = False

    async def __call__(self, scope, receive, send) -> None:
        self.called = True
        while True:
            message = await receive()
            if not message.get("more_body"):
                break
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})


async def _run_middleware(app, *, chunks: list[bytes], content_length: str | None, method="POST"):
    middleware = EphemeralRequestBodyLimitMiddleware(app)
    headers = [] if content_length is None else [(b"content-length", content_length.encode())]
    scope = {"type": "http", "method": method, "headers": headers, "path": "/check"}

    queue = list(chunks)

    async def receive():
        body = queue.pop(0) if queue else b""
        return {"type": "http.request", "body": body, "more_body": bool(queue)}

    sent: list[dict] = []

    async def send(message):
        sent.append(message)

    await middleware(scope, receive, send)
    return sent


def _status(sent: list[dict]) -> int:
    return next(m["status"] for m in sent if m["type"] == "http.response.start")


async def test_declared_oversize_body_is_rejected_before_the_app_runs() -> None:
    app = _Recorder()

    sent = await _run_middleware(
        app, chunks=[b"x"], content_length=str(MAX_REQUEST_BODY_BYTES + 1)
    )

    assert _status(sent) == 413
    assert not app.called, "the app must never see an oversized body"


async def test_body_exceeding_the_cap_mid_stream_is_rejected() -> None:
    """A missing or dishonest content-length is caught while streaming."""

    sent = await _run_middleware(
        _Recorder(),
        chunks=[b"x" * (MAX_REQUEST_BODY_BYTES // 2 + 1)] * 2,
        content_length=None,
    )

    assert _status(sent) == 413


async def test_body_within_the_cap_reaches_the_app() -> None:
    app = _Recorder()

    sent = await _run_middleware(app, chunks=[b"small"], content_length="5")

    assert _status(sent) == 200
    assert app.called


async def test_unparseable_content_length_falls_back_to_streaming_enforcement() -> None:
    app = _Recorder()

    sent = await _run_middleware(app, chunks=[b"small"], content_length="not-a-number")

    assert _status(sent) == 200
    assert app.called


async def test_non_mutating_methods_bypass_the_cap() -> None:
    app = _Recorder()

    sent = await _run_middleware(
        app, chunks=[b""], content_length=str(MAX_REQUEST_BODY_BYTES + 1), method="GET"
    )

    assert _status(sent) == 200
    assert app.called


# ── same-origin ─────────────────────────────────────────────────────────────


def test_matching_origin_is_accepted() -> None:
    require_same_origin(_request(headers={"origin": "https://avvalo.uz"}))


def test_request_without_origin_metadata_is_allowed_through() -> None:
    """Non-browser clients carry no origin; per-IP limits still apply to them."""

    require_same_origin(_request())


def test_sec_fetch_site_cross_site_is_rejected() -> None:
    with pytest.raises(HTTPException) as exc:
        require_same_origin(_request(headers={"sec-fetch-site": "cross-site"}))

    assert exc.value.status_code == 403


@pytest.mark.parametrize(
    "origin",
    [
        "https://evil.example",
        "http://avvalo.uz",  # scheme mismatch
        "https://avvalo.uz:8443",  # port mismatch
        "https://user@avvalo.uz",  # userinfo smuggling
        "https://avvalo.uz/path",  # path present
        "https://avvalo.uz?q=1",  # query present
        "ftp://avvalo.uz",  # unsupported scheme
    ],
)
def test_mismatched_or_malformed_origins_are_rejected(origin: str) -> None:
    with pytest.raises(HTTPException) as exc:
        require_same_origin(_request(headers={"origin": origin}))

    assert exc.value.status_code == 403


def test_forwarded_proto_is_honoured_when_matching_the_origin_scheme() -> None:
    """Behind TLS termination the socket is http but the public origin is https."""

    request = _request(
        headers={"origin": "https://avvalo.uz", "x-forwarded-proto": "https"},
        scheme="http",
    )

    require_same_origin(request)


def test_trailing_dot_host_matches_its_canonical_form() -> None:
    require_same_origin(_request(headers={"origin": "https://avvalo.uz."}))


# ── upload cap ──────────────────────────────────────────────────────────────


def _upload(content: bytes, *, filename: str | None = "photo.png") -> UploadFile:
    return UploadFile(file=BytesIO(content), filename=filename, size=len(content))


async def test_missing_upload_is_not_an_error() -> None:
    assert await read_limited_upload(None) is None


async def test_upload_without_a_filename_is_ignored() -> None:
    assert await read_limited_upload(_upload(b"data", filename=None)) is None


async def test_empty_upload_is_treated_as_absent() -> None:
    assert await read_limited_upload(_upload(b"")) is None


async def test_upload_within_the_cap_is_returned() -> None:
    assert await read_limited_upload(_upload(b"png-bytes")) == b"png-bytes"


async def test_oversized_upload_is_rejected_with_413() -> None:
    with pytest.raises(HTTPException) as exc:
        await read_limited_upload(_upload(b"x" * (MAX_UPLOAD_BYTES + 1)))

    assert exc.value.status_code == 413


# ── Turnstile ───────────────────────────────────────────────────────────────


class _Settings:
    def __init__(self, secret) -> None:
        self.turnstile_secret = secret


class _Secret:
    def __init__(self, value: str) -> None:
        self.value = value

    def get_secret_value(self) -> str:
        return self.value


async def test_text_only_check_does_not_require_turnstile() -> None:
    await require_turnstile_for_image(
        image_bytes=None, token=None, request=_request(), settings=_Settings(None)
    )


async def test_image_check_is_refused_when_turnstile_is_unconfigured() -> None:
    """Without a secret the challenge cannot be verified, so images stay off."""

    with pytest.raises(HTTPException) as exc:
        await require_turnstile_for_image(
            image_bytes=b"png", token="tok", request=_request(), settings=_Settings(None)
        )

    assert exc.value.status_code == 400


async def test_image_check_is_refused_when_the_token_fails(monkeypatch) -> None:
    monkeypatch.setattr("app.web.abuse.verify_turnstile", _always(False))

    with pytest.raises(HTTPException) as exc:
        await require_turnstile_for_image(
            image_bytes=b"png",
            token="bad",
            request=_request(),
            settings=_Settings(_Secret("s")),
        )

    assert exc.value.status_code == 400


async def test_image_check_passes_with_a_solved_token(monkeypatch) -> None:
    monkeypatch.setattr("app.web.abuse.verify_turnstile", _always(True))

    await require_turnstile_for_image(
        image_bytes=b"png", token="good", request=_request(), settings=_Settings(_Secret("s"))
    )


def _always(value: bool):
    async def _stub(**_kwargs) -> bool:
        return value

    return _stub


async def test_absent_token_is_never_sent_for_verification() -> None:
    assert await verify_turnstile(token=None, secret="s", remote_ip=None) is False
    assert await verify_turnstile(token="", secret="s", remote_ip=None) is False


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> None:
        return None


@pytest.mark.parametrize(
    ("payload", "expected"),
    [({"success": True}, True), ({"success": False}, False), ({}, False)],
)
def test_turnstile_response_success_flag_decides_the_result(
    monkeypatch, payload: dict, expected: bool
) -> None:
    monkeypatch.setattr("app.web.abuse.urlopen", lambda *a, **k: _FakeResponse(payload))

    assert _verify_turnstile_sync("tok", "secret", "203.0.113.9") is expected


def test_turnstile_network_failure_fails_closed(monkeypatch) -> None:
    def _boom(*_args, **_kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr("app.web.abuse.urlopen", _boom)

    assert _verify_turnstile_sync("tok", "secret", None) is False


# ── rate-limit peer resolution ──────────────────────────────────────────────


def test_socket_peer_is_used_when_no_proxy_is_in_front() -> None:
    assert client_ip_from_request(_request(client=("203.0.113.9", 1))) == "203.0.113.9"


def test_untrusted_peer_cannot_forge_its_own_rate_limit_key() -> None:
    """A public peer's proxy headers must be ignored, or limits are bypassable.

    The peer here is a genuinely global address on purpose: Python's
    ``ipaddress`` reports the documentation ranges (``203.0.113.0/24``,
    ``198.51.100.0/24``) as *private*, so using one as the "untrusted" peer
    would silently take the trusted-proxy branch and assert nothing.
    """

    request = _request(
        headers={"x-real-ip": "8.8.4.4", "x-forwarded-for": "1.1.1.1"},
        client=("8.8.8.8", 1),
    )

    assert client_ip_from_request(request) == "8.8.8.8"


def test_trusted_proxy_x_real_ip_is_honoured() -> None:
    request = _request(headers={"x-real-ip": "198.51.100.7"}, client=("127.0.0.1", 1))

    assert client_ip_from_request(request) == "198.51.100.7"


def test_trusted_proxy_uses_the_rightmost_valid_forwarded_for_entry() -> None:
    """The rightmost entry is the one the trusted proxy itself observed."""

    request = _request(
        headers={"x-forwarded-for": "10.0.0.1, garbage, 198.51.100.7"},
        client=("127.0.0.1", 1),
    )

    assert client_ip_from_request(request) == "198.51.100.7"


def test_trusted_proxy_with_unusable_headers_falls_back_to_the_peer() -> None:
    request = _request(headers={"x-forwarded-for": "not-an-ip"}, client=("127.0.0.1", 1))

    assert client_ip_from_request(request) == "127.0.0.1"


def test_request_without_a_client_has_no_peer() -> None:
    assert client_ip_from_request(_request(client=None)) is None


def test_ip_key_is_pseudonymous_and_stable() -> None:
    request = _request(client=("203.0.113.9", 1))

    first = pseudonymous_ip_key(request, secret="s")
    second = pseudonymous_ip_key(request, secret="s")

    assert first == second
    assert first is not None
    assert "203.0.113.9" not in first, "the raw IP must never appear in the key"


def test_ip_key_changes_with_the_secret() -> None:
    request = _request(client=("203.0.113.9", 1))

    assert pseudonymous_ip_key(request, secret="a") != pseudonymous_ip_key(request, secret="b")


def test_ip_key_is_absent_without_a_peer() -> None:
    assert pseudonymous_ip_key(_request(client=None), secret="s") is None
