"""Deterministic composition of reviewed card wording into a draft (§4).

Reviewed card text used to reach the user only as a suggestion in the answer
prompt, so what they read was always a paraphrase. Where a card carries wording
approved in the reply language, those sentences are emitted verbatim and the
model's contribution is reduced to what only it can do: the situation-specific
``pattern`` sentence and any warning sign the cards do not already cover.

Composed bullets are prepended, never appended: the validator truncates each
block to three, so ordering is what decides that reviewed wording survives and a
model paraphrase is what gets cut.

Composition happens *before* validation. A card is reviewed, not trusted — the
full safety chassis still runs over the composed answer.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence

from app.engine.knowledge.types import KnowledgeCard
from app.engine.types import DraftOutput, Evidence, Language


def compose_card_text(
    draft: DraftOutput,
    cards: Sequence[KnowledgeCard],
    *,
    mandatory_card_ids: Sequence[str],
    language: Language,
) -> DraftOutput:
    """Merge reviewed wording from mandatory cards into ``draft``.

    Only cards selected by a rule or signal trigger contribute: an alias-cue or
    router match is a relevance guess, and promoting a guess to verbatim output
    would state something the check never actually detected.

    Returns ``draft`` unchanged when no mandatory card carries wording for this
    language, which is the case for every card that has not yet been through
    native review.
    """

    mandatory = set(mandatory_card_ids)
    contributing = [
        card
        for card in cards
        if card.id in mandatory and language.value in card.localized
    ]
    if not contributing:
        return draft

    composed_flags: list[Evidence] = []
    composed_verify: list[str] = []
    composed_ask: list[str] = []
    for card in contributing:
        text = card.localized[language.value]
        composed_flags.extend(
            Evidence(text=flag, source_id=card.id) for flag in text.red_flags
        )
        composed_verify.extend(text.verify_steps)
        composed_ask.extend(text.questions)

    return draft.model_copy(
        update={
            "red_flags": _merge_evidence(composed_flags, draft.red_flags),
            "verify": _merge(composed_verify, draft.verify),
            "ask": _merge(composed_ask, draft.ask),
        }
    )


def _merge_evidence(
    composed: list[Evidence], model_authored: list[Evidence]
) -> list[Evidence]:
    seen = {_key(item.text) for item in composed}
    kept = [item for item in model_authored if _key(item.text) not in seen]
    return [*composed, *kept]


def _merge(composed: list[str], model_authored: list[str]) -> list[str]:
    seen = {_key(item) for item in composed}
    kept = [item for item in model_authored if _key(item) not in seen]
    return [*composed, *kept]


def _key(text: str) -> str:
    """Normalize for duplicate detection only; never for display.

    Catches a model echoing a composed bullet back with different casing,
    spacing, or trailing punctuation. Genuine paraphrases still slip through —
    truncation to three bullets is what bounds those.
    """

    folded = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"[\s\W_]+", " ", folded).strip()
