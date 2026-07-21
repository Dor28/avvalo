"""Deterministic, bounded retrieval over reviewed knowledge cards."""

from __future__ import annotations

from app.engine.knowledge.loader import FileKnowledgeStore
from app.engine.knowledge.types import (
    KnowledgeLookupError,
    KnowledgeRouter,
    KnowledgeStore,
    RetrievalResult,
    RouterResponse,
)
from app.engine.rules import normalize_text
from app.engine.types import RuleHit, Signal

_MAX_CARDS = 3


async def retrieve_knowledge(
    *,
    face_id: str,
    minimized_text: str,
    rule_hits: list[RuleHit],
    signals: list[Signal],
    store: KnowledgeStore | None = None,
    router: KnowledgeRouter | None = None,
) -> RetrievalResult:
    """Select at most three cards; invalid router IDs never reach lookup/prompt."""

    try:
        knowledge_base = (store or FileKnowledgeStore()).load(face_id)
    except KnowledgeLookupError:
        return RetrievalResult(status="unavailable")

    cards_by_id = {card.id: card for card in knowledge_base.cards}
    rule_ids = {hit.rule_id for hit in rule_hits}
    signal_kinds = {signal.kind for signal in signals}
    mandatory_ids = {
        card.id
        for card in knowledge_base.cards
        if rule_ids.intersection(card.trigger_rule_ids)
        or signal_kinds.intersection(card.trigger_signal_kinds)
    }

    normalized_text = normalize_text(minimized_text)
    cue_scores: dict[str, int] = {}
    for card in knowledge_base.cards:
        aliases = {
            normalize_text(alias)
            for values in card.retrieval_aliases.values()
            for alias in values
            if alias.strip()
        }
        matches = sum(1 for alias in aliases if alias and alias in normalized_text)
        if matches:
            cue_scores[card.id] = matches

    deterministic_ids = mandatory_ids | set(cue_scores)
    rule_triggered = any(
        rule_ids.intersection(card.trigger_rule_ids) for card in knowledge_base.cards
    )
    mode = "rule" if rule_triggered else "signal"
    if not mandatory_ids:
        mode = "cue" if cue_scores else "none"

    invalid_router_ids: tuple[str, ...] = ()
    status = "ok" if deterministic_ids else "empty"
    router_status = "not_used"
    router_ids: list[str] = []
    router_input_tokens = 0
    router_output_tokens = 0
    # Deterministic matches are already ranked from authoritative rules/signals and
    # reviewed aliases. Calling a paid router here would add cost without changing
    # the first three selected cards, so the router is reserved for empty recall.
    if router is not None and not deterministic_ids:
        try:
            routed = await router.route(
                face_id=face_id,
                minimized_text=minimized_text,
                allowed_ids=tuple(sorted(cards_by_id)),
                max_results=_MAX_CARDS,
            )
        except Exception:
            router_status = "unavailable"
        else:
            # Keep older injected fakes source-compatible while the production
            # protocol returns RouterResponse with cost metadata.
            response = (
                routed
                if isinstance(routed, RouterResponse)
                else RouterResponse(card_ids=list(routed))
            )
            proposed = response.card_ids
            router_input_tokens = response.input_tokens
            router_output_tokens = response.output_tokens
            invalid_router_ids = tuple(
                dict.fromkeys(card_id for card_id in proposed if card_id not in cards_by_id)
            )
            router_ids = list(
                dict.fromkeys(card_id for card_id in proposed if card_id in cards_by_id)
            )[:_MAX_CARDS]
            router_status = "invalid_ids" if invalid_router_ids else "ok"
            if router_ids:
                status = "ok"
            if not deterministic_ids and router_ids:
                mode = "router"

    ranked_ids = sorted(
        deterministic_ids,
        key=lambda card_id: (
            0 if card_id in mandatory_ids else 1,
            -cue_scores.get(card_id, 0),
            card_id,
        ),
    )
    selected_ids = list(dict.fromkeys([*ranked_ids, *router_ids]))[:_MAX_CARDS]
    cards = tuple(cards_by_id[card_id] for card_id in selected_ids)
    if not cards and status == "ok":
        status = "empty"
    return RetrievalResult(
        cards=cards,
        mode=mode,
        status=status,
        router_status=router_status,
        kb_version=knowledge_base.version,
        invalid_router_ids=invalid_router_ids,
        router_input_tokens=router_input_tokens,
        router_output_tokens=router_output_tokens,
    )
