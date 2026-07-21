"""SQLAlchemy-backed hash-only URL reputation lookup."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.models import URLBlocklist
from app.engine.url_reputation.types import URLReputationMatch


class DatabaseURLReputationStore:
    """Batch exact-match lookup against the local public-feed mirror."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def lookup(self, domain_hashes: tuple[str, ...]) -> list[URLReputationMatch]:
        if not domain_hashes:
            return []
        rows = (
            await self._session.execute(
                select(
                    URLBlocklist.domain_hash,
                    URLBlocklist.source,
                    URLBlocklist.first_seen,
                ).where(URLBlocklist.domain_hash.in_(domain_hashes))
            )
        ).all()
        return [
            URLReputationMatch(
                domain_hash=domain_hash,
                source=source,
                first_seen=first_seen,
            )
            for domain_hash, source, first_seen in rows
        ]
