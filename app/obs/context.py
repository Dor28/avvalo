"""Anonymous request correlation for privacy-safe local logs.

Request IDs are generated inside Avvalo, are unrelated to a user identity, and
live only for one web request, Telegram update, or direct engine call. They let
operators connect start, error, and completion records without storing content.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from secrets import token_hex
from typing import ParamSpec, TypeVar

REQUEST_ID_RE = re.compile(r"^[0-9a-f]{32}$")

_CURRENT_REQUEST_ID: ContextVar[str | None] = ContextVar(
    "avvalo_request_id",
    default=None,
)
_P = ParamSpec("_P")
_R = TypeVar("_R")


def current_request_id() -> str | None:
    """Return the request ID bound to the current async execution context."""

    return _CURRENT_REQUEST_ID.get()


@contextmanager
def request_context(request_id: str | None = None) -> Iterator[str]:
    """Bind a server-generated request ID until the context exits."""

    resolved = token_hex(16) if request_id is None else request_id
    if REQUEST_ID_RE.fullmatch(resolved) is None:
        raise ValueError("request_id must be 32 lowercase hexadecimal characters")

    token = _CURRENT_REQUEST_ID.set(resolved)
    try:
        yield resolved
    finally:
        _CURRENT_REQUEST_ID.reset(token)


@contextmanager
def ensure_request_context() -> Iterator[str]:
    """Reuse an existing request ID or create one for a direct engine call."""

    existing = current_request_id()
    if existing is not None:
        yield existing
        return

    with request_context() as request_id:
        yield request_id


def with_request_context(
    func: Callable[_P, Awaitable[_R]],
) -> Callable[_P, Awaitable[_R]]:
    """Wrap one async operation in an anonymous correlation context."""

    @wraps(func)
    async def wrapped(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        with ensure_request_context():
            return await func(*args, **kwargs)

    return wrapped
