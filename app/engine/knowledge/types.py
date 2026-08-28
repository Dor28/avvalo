"""Typed contracts for reviewed knowledge retrieval."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, Field


class LocalizedCardText(BaseModel):
    """Reviewer-approved card wording in one reply language.

    The untranslated card fields are English and exist to ground the model's
    prompt. These are the sentences a user actually reads, so a card carrying
    them can be composed into the answer verbatim rather than paraphrased
    (PIPELINE_V2 §4).
    """

    red_flags: list[str] = Field(default_factory=list)
    verify_steps: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)


class KnowledgeCard(BaseModel):
    """One versioned, reviewed pattern or verification card."""

    id: str
    version: str
    status: Literal["approved", "draft", "retired"]
    reviewer: str
    trigger_rule_ids: list[str] = Field(default_factory=list)
    trigger_signal_kinds: list[str] = Field(default_factory=list)
    retrieval_aliases: dict[str, list[str]] = Field(default_factory=dict)
    mechanism: str
    red_flags: list[str] = Field(default_factory=list)
    verify_steps: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    reviewed_case_ids: list[str] = Field(default_factory=list)
    # Keyed by ``Language`` value ("uz_latn" / "ru"). Absent until a native
    # reviewer supplies the wording, in which case the model localizes the card
    # as before — so this is additive per card, never a flag day.
    localized: dict[str, LocalizedCardText] = Field(default_factory=dict)


class KnowledgeBase(BaseModel):
    """Approved cards and their deploy-visible version."""

    version: str
    cards: tuple[KnowledgeCard, ...]


class RetrievalResult(BaseModel):
    """Bounded knowledge selected for one ephemeral check."""

    cards: tuple[KnowledgeCard, ...] = ()
    mode: Literal["rule", "signal", "cue", "router", "none"] = "none"
    status: Literal["ok", "empty", "unavailable"] = "empty"
    router_status: Literal["not_used", "ok", "unavailable", "invalid_ids"] = "not_used"
    kb_version: str | None = None
    # Cards selected by a rule/signal trigger rather than an alias cue or the
    # router. Only these may compose their reviewed wording into the answer
    # verbatim: a cue or router match is a relevance guess, not detected evidence.
    mandatory_card_ids: tuple[str, ...] = ()
    invalid_router_ids: tuple[str, ...] = ()
    router_input_tokens: int = Field(default=0, ge=0)
    router_output_tokens: int = Field(default=0, ge=0)

    @property
    def knowledge_card_ids(self) -> list[str]:
        return [card.id for card in self.cards]

    @property
    def reviewed_case_ids(self) -> list[str]:
        return list(
            dict.fromkeys(case_id for card in self.cards for case_id in card.reviewed_case_ids)
        )


class KnowledgeStore(Protocol):
    """Load approved cards without accepting user content."""

    def load(self) -> KnowledgeBase: ...


class KnowledgeRouter(Protocol):
    """Optional allowlisted recall helper over minimized text only."""

    async def route(
        self,
        *,
        minimized_text: str,
        allowed_ids: tuple[str, ...],
        max_results: int,
    ) -> RouterResponse: ...


class RouterResponse(BaseModel):
    """Allowlisted card proposals plus router token usage."""

    card_ids: list[str] = Field(default_factory=list)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)


class KnowledgeLookupError(RuntimeError):
    """The versioned knowledge files could not be loaded safely."""
