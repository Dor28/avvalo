"""Merge database card overrides onto the shipped YAML base and publish them.

The merge is by card ID: an override with a baseline card's ID replaces it, an
override with a new ID adds a card, and a ``draft``/``retired`` override
suppresses the baseline card of that ID (the loader already drops non-approved
cards). Wholesale replacement was rejected for the same reason as the rule pack:
it would force an operator to re-enter the entire base before adding one card.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.engine.knowledge import retrieve_knowledge
from app.engine.knowledge.loader import (
    load_yaml_knowledge_base,
    set_active_knowledge_base,
)
from app.engine.knowledge.types import KnowledgeBase
from app.engine.minimize import minimize
from app.engine.rules import run_rules
from app.knowledge_store.repo import KnowledgeCardDraft, LoadedOverrides, load_overrides
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


@dataclass(frozen=True)
class CardPreview:
    """What retrieval would do with an unsaved card, for the operator dry-run."""

    selected: bool
    mode: str
    status: str
    other_card_ids: tuple[str, ...]
    not_approved: bool


class _StaticKnowledgeStore:
    """Serve one in-memory base so a preview never touches the database."""

    def __init__(self, base: KnowledgeBase) -> None:
        self._base = base

    def load(self) -> KnowledgeBase:
        return self._base


async def preview_card(
    draft: KnowledgeCardDraft, sample: str, base: KnowledgeBase
) -> CardPreview:
    """Report whether ``draft`` would actually be retrieved for ``sample``.

    A card can be well formed, save cleanly, and still never be retrieved,
    because selection runs on trigger IDs and aliases rather than on the card
    body. This drives the real ``retrieve_knowledge`` over an in-memory merge so
    the answer cannot drift from production. The router is never invoked, so the
    dry-run is deterministic and free. Raises ``ValueError`` on an invalid draft.
    """

    card = draft.as_card()
    without_card = tuple(existing for existing in base.cards if existing.id != card.id)
    # A non-approved card is absent from retrieval entirely; keep it out so the
    # preview shows what the operator would really get.
    candidate = (*without_card, card) if card.status == "approved" else without_card

    rule_hits, signals = run_rules(sample)
    result = await retrieve_knowledge(
        minimized_text=minimize(sample, signals),
        rule_hits=rule_hits,
        signals=signals,
        store=_StaticKnowledgeStore(KnowledgeBase(version=base.version, cards=candidate)),
        router=None,
    )

    selected_ids = tuple(result.knowledge_card_ids)
    return CardPreview(
        selected=card.id in selected_ids,
        mode=result.mode,
        status=card.status,
        other_card_ids=tuple(other for other in selected_ids if other != card.id),
        not_approved=card.status != "approved",
    )


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
        cards=tuple(merged),
    )


async def refresh_knowledge_base(session: AsyncSession) -> KnowledgeBase:
    """Merge the stored card overrides onto the YAML baseline and publish it."""

    base = load_yaml_knowledge_base()
    overrides = await load_overrides(session)
    merged = merge_knowledge_base(base, overrides)
    set_active_knowledge_base(merged)
    log_event(
        "knowledge_base_refreshed",
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
    """Refresh the base, leaving the previous one in force on failure."""

    try:
        async with session_factory() as session:
            await refresh_knowledge_base(session)
    except Exception as exc:
        # Never propagate into the scheduler. The base already in force
        # (merged or YAML baseline) keeps answering checks; an empty base
        # would look healthy while silently answering with no knowledge.
        log_error(stage="knowledge", error_type=type(exc).__name__)


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
