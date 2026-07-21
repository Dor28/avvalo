"""Typed contracts for the local, hash-only URL reputation stage."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Protocol

from pydantic import BaseModel


class URLReputationMatch(BaseModel):
    """One local exact-match result; never contains a raw URL or domain."""

    domain_hash: str
    source: Literal["urlhaus", "openphish", "uz_local"]
    first_seen: datetime


class URLReputationStore(Protocol):
    """Batch lookup interface used by the pipeline and offline fakes."""

    async def lookup(self, domain_hashes: tuple[str, ...]) -> list[URLReputationMatch]: ...
