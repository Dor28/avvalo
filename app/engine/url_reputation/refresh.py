"""Scheduled local-feed refresh for R6.

Feeds are downloaded in a background job, never during a user check. Google
Safe Browsing Lookup is deliberately not used because it would disclose the
submitted URL; the hash-prefix Update API remains deferred for v1 complexity.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen

import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.data.models import URLBlocklist
from app.engine.url_reputation.normalize import hash_domain, normalize_domain

LOGGER = logging.getLogger(__name__)
_REPO_ROOT = Path(__file__).resolve().parents[3]
_OWN_LIST_PATH = _REPO_ROOT / "rules" / "shared" / "uz_phishing_domains.yaml"
FeedFetcher = Callable[[str], Awaitable[str]]
_UPSERT_BATCH_SIZE = 1_000


@dataclass(frozen=True)
class RefreshResult:
    """Aggregate-only refresh outcome."""

    entries: int = 0
    sources: int = 0
    disabled: bool = False


async def refresh_url_blocklist(
    session: AsyncSession,
    *,
    settings: Settings,
    fetcher: FeedFetcher | None = None,
    now: datetime | None = None,
    own_list_path: Path = _OWN_LIST_PATH,
) -> RefreshResult:
    """Refresh configured public feeds and the founder-curated local list."""

    if not settings.url_reputation_enabled:
        return RefreshResult(disabled=True)
    fetch = fetcher or _fetch_text
    now = _utc(now)
    source_domains: dict[str, set[str]] = {
        "uz_local": _load_own_domains(own_list_path),
    }
    for source, url in (
        ("urlhaus", settings.urlhaus_feed_url),
        ("openphish", settings.openphish_feed_url),
    ):
        if url:
            try:
                payload = await fetch(url)
            except Exception:
                # A scheduled feed outage never reaches or slows a user check.
                # Log only the static source ID, never exception text or feed data.
                LOGGER.warning("url reputation feed unavailable source=%s", source)
                continue
            source_domains[source] = _parse_feed(payload)

    entries = 0
    for source, domains in source_domains.items():
        domain_hashes = sorted(hash_domain(domain) for domain in domains)
        await _upsert_hashes(
            session,
            source=source,
            domain_hashes=domain_hashes,
            now=now,
        )
        entries += len(domain_hashes)
    await session.flush()
    return RefreshResult(entries=entries, sources=len(source_domains))


async def run_url_reputation_refresh_job(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    *,
    fetcher: FeedFetcher | None = None,
) -> RefreshResult:
    """Run one scheduled refresh transaction."""

    async with session_factory() as session:
        result = await refresh_url_blocklist(session, settings=settings, fetcher=fetcher)
        await session.commit()
    LOGGER.info(
        "url reputation refresh completed entries=%s sources=%s",
        result.entries,
        result.sources,
    )
    return result


def install_url_reputation_job(
    scheduler: AsyncIOScheduler,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    """Install R6 on the existing in-process scheduler."""

    if not settings.url_reputation_enabled:
        return
    scheduler.add_job(
        run_url_reputation_refresh_job,
        "interval",
        args=[session_factory, settings],
        hours=settings.url_feeds_refresh_hours,
        next_run_time=datetime.now(UTC),
        id="url_reputation_refresh",
        replace_existing=True,
    )


async def _fetch_text(url: str) -> str:
    return await asyncio.to_thread(_fetch_text_sync, url)


def _fetch_text_sync(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Avvalo/1.0 URL reputation refresh"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def _parse_feed(payload: str) -> set[str]:
    domains: set[str] = set()
    candidates = re.findall(
        r"(?i)(?:hxxps?|https?)://[^,\s\"']+|(?:www\.)?[a-z0-9.-]+\.[a-z]{2,}",
        payload,
    )
    for candidate in candidates:
        domain = normalize_domain(candidate)
        if domain:
            domains.add(domain)
    return domains


def _load_own_domains(path: Path) -> set[str]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    values = data.get("domains", []) if isinstance(data, dict) else []
    if not isinstance(values, list):
        raise ValueError("UZ phishing domain list must contain a domains list")
    return {
        domain
        for value in values
        if isinstance(value, str) and (domain := normalize_domain(value)) is not None
    }


async def _upsert_hashes(
    session: AsyncSession,
    *,
    source: str,
    domain_hashes: list[str],
    now: datetime,
) -> None:
    """Upsert a large feed in bounded statements, preserving first_seen."""

    if not domain_hashes:
        return
    dialect = session.bind.dialect.name
    for start in range(0, len(domain_hashes), _UPSERT_BATCH_SIZE):
        rows = [
            {
                "domain_hash": domain_hash,
                "source": source,
                "first_seen": now,
                "last_seen": now,
            }
            for domain_hash in domain_hashes[start : start + _UPSERT_BATCH_SIZE]
        ]
        if dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert

            statement = insert(URLBlocklist).values(rows)
        elif dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert

            statement = insert(URLBlocklist).values(rows)
        else:
            for row_data in rows:
                row = await session.get(
                    URLBlocklist,
                    (row_data["domain_hash"], source),
                )
                if row is None:
                    session.add(URLBlocklist(**row_data))
                else:
                    row.last_seen = now
            continue
        await session.execute(
            statement.on_conflict_do_update(
                index_elements=["domain_hash", "source"],
                set_={"last_seen": now},
            )
        )


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
