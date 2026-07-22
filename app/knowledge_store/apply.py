"""Merge database card overrides onto the shipped YAML base and publish them.

The merge is by card ID: an override with a baseline card's ID replaces it, an
override with a new ID adds a card, and a ``draft``/``retired`` override
suppresses the baseline card of that ID (the loader already drops non-approved
cards). Wholesale replacement was rejected for the same reason as the rule pack:
it would force an operator to re-enter the entire base before adding one card.
"""

from __future__ import annotations

from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.engine.faces import FACES
from app.engine.knowledge.loader import (
    load_yaml_knowledge_base,
    set_active_knowledge_base,
)
from app.engine.knowledge.types import KnowledgeBase
from app.knowledge_store.repo import LoadedOverrides, load_overrides
from app.obs.events import log_error, log_event

# ``app.data.repo.VERSION_RE`` rejects a kb_version outside
# ``[A-Za-z0-9][A-Za-z0-9_.-]{0,79}``, and a rejected version raises on every
# check_event write — after the model has already been paid for. Dots and digits
# are inside that class; ``+``, ``:`` and spaces are not.
_DB_VERSION_FORMAT = "%Y%m%d%H%M%S"
_KB_VERSION_MAX_CHARS = 80


def derive_kb_version(base_version: str, latest_updated_ts: datetime | None) -> str:
    """Stamp the merged base so telemetry can tell which knowledge answered."""

    if latest_updated_ts is None:
        return base_version
    stamped = f"{base_version}.db{latest_updated_ts.astimezone(UTC):{_DB_VERSION_FORMAT}}"
    # Fail back to the baseline version rather than emit something unwritable.
    return stamped if len(stamped) <= _KB_VERSION_MAX_CHARS else base_version


def merge_knowledge_base(base: KnowledgeBase, overrides: LoadedOverrides) -> KnowledgeBase:
    """Overlay ``overrides`` onto ``base`` by card ID, preserving base order."""

    by_id = {card.id: card for card in overrides.approved}
    merged = []
    for card in base.cards:
        if card.id in overrides.suppressed_ids:
            continue
        merged.append(by_id.pop(card.id, card))
    # Whatever is left introduces a card the YAML baseline does not define.
    merged.extend(card for card in by_id.values() if card.id not in overrides.suppressed_ids)

    return KnowledgeBase(
        version=derive_kb_version(base.version, overrides.latest_updated_ts),
        face=base.face,
        cards=tuple(merged),
    )


async def refresh_knowledge_base(session: AsyncSession, face_id: str) -> KnowledgeBase:
    """Merge one face's card overrides onto its YAML baseline and publish it."""

    base = load_yaml_knowledge_base(face_id)
    overrides = await load_overrides(session, face=face_id)
    merged = merge_knowledge_base(base, overrides)
    set_active_knowledge_base(face_id, merged)
    log_event(
        "knowledge_base_refreshed",
        face=face_id,
        baseline_cards=len(base.cards),
        override_cards=len(overrides.approved),
        suppressed_cards=len(overrides.suppressed_ids),
        active_cards=len(merged.cards),
        kb_version=merged.version,
    )
    return merged


async def run_knowledge_refresh_job(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Refresh every face's base, leaving the previous one in force on failure."""

    for face_id in FACES:
        try:
            async with session_factory() as session:
                await refresh_knowledge_base(session, face_id)
        except Exception as exc:
            # Never propagate into the scheduler. The base already in force
            # (merged or YAML baseline) keeps answering checks; an empty base
            # would look healthy while silently answering with no knowledge.
            log_error(
                stage="knowledge",
                error_type=type(exc).__name__,
                face=face_id,
            )


def install_knowledge_refresh_job(
    scheduler: AsyncIOScheduler,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    """Install the periodic knowledge refresh on the existing in-process scheduler."""

    scheduler.add_job(
        run_knowledge_refresh_job,
        "interval",
        args=[session_factory],
        minutes=settings.knowledge_refresh_minutes,
        next_run_time=datetime.now(UTC),
        id="knowledge_base_refresh",
        replace_existing=True,
    )
