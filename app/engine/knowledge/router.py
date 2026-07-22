"""Allowlisted semantic knowledge router over minimized text (§8.1).

The router is a recall helper only. It receives minimized text, proposes IDs
from a server-provided allowlist, and never emits user-facing facts or verdicts.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field, ValidationError

from app.config import Settings
from app.engine.knowledge.types import RouterResponse
from app.engine.llm.base import LLMResponseFormatError
from app.engine.llm.openai_compat import OpenAICompatibleProvider

_MAX_ROUTER_OUTPUT_TOKENS = 200


class _RouterDraft(BaseModel):
    card_ids: list[str] = Field(default_factory=list)
    unmatched: bool = False


class OpenAICompatibleKnowledgeRouter:
    """Route minimized text using the existing OpenAI-compatible adapter."""

    def __init__(self, provider: OpenAICompatibleProvider) -> None:
        self._provider = provider

    @classmethod
    def from_settings(cls, settings: Settings) -> OpenAICompatibleKnowledgeRouter:
        """Build the explicitly enabled router or raise a safe config error."""

        base_url = settings.knowledge_router_base_url
        api_key = settings.knowledge_router_api_key
        model = settings.knowledge_router_model
        if not (
            base_url
            and api_key is not None
            and api_key.get_secret_value()
            and model
        ):
            raise ValueError("knowledge router is enabled but its provider config is incomplete")
        return cls(
            OpenAICompatibleProvider(
                base_url=base_url,
                api_key=api_key,
                model=model,
                timeout_s=settings.knowledge_router_timeout_s,
                temperature=0.0,
            )
        )

    async def route(
        self,
        *,
        minimized_text: str,
        allowed_ids: tuple[str, ...],
        max_results: int,
    ) -> RouterResponse:
        """Return bounded proposals; backend retrieval still validates every ID."""

        system = (
            "You are a recall router. Select potentially relevant reviewed knowledge "
            "card IDs. Return JSON only. Never make a safety judgment, red flag, or verdict. "
            "Use only IDs in the supplied allowlist. If none fit, set unmatched=true."
        )
        user = json.dumps(
            {
                "minimized_text": minimized_text,
                "allowed_ids": list(allowed_ids),
                "max_results": min(3, max_results),
                "output": {"card_ids": ["allowed.id"], "unmatched": False},
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        completion = await self._provider.complete_json(
            system=system,
            user=user,
            schema=_RouterDraft.model_json_schema(),
            max_output_tokens=_MAX_ROUTER_OUTPUT_TOKENS,
        )
        try:
            draft = _RouterDraft.model_validate(completion.payload)
        except ValidationError as exc:
            raise LLMResponseFormatError("Router response did not match its JSON schema") from exc
        ids = [] if draft.unmatched else list(dict.fromkeys(draft.card_ids))[:max_results]
        return RouterResponse(
            card_ids=ids,
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
        )
