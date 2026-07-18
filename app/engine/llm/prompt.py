"""Prompt assembly for Avvalo LLM calls."""

from __future__ import annotations

import json
from collections.abc import Sequence
from functools import cache
from pathlib import Path

from app.engine.faces import FACES
from app.engine.knowledge import KnowledgeCard
from app.engine.rules import load_rule_pack
from app.engine.types import DraftOutput, Language, RuleHit, Signal

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SYSTEM_PROMPT = _REPO_ROOT / "prompts" / "system_safety.txt"


def build_prompt(
    *,
    face_id: str,
    language: Language,
    minimized_text: str,
    rule_hits: list[RuleHit],
    signals: list[Signal],
    knowledge_cards: Sequence[KnowledgeCard] = (),
) -> tuple[str, str]:
    """Render the system and face prompt for one check."""

    try:
        face = FACES[face_id]
    except KeyError as exc:
        raise ValueError(f"Unknown face: {face_id}") from exc

    system = _read_prompt(_SYSTEM_PROMPT)
    template = _read_prompt(_REPO_ROOT / face.prompt_template)
    user = template.format(
        language=language.value,
        minimized_text=minimized_text,
        rule_hits=_render_rule_hits(face_id, rule_hits),
        signals=_render_signals(signals),
        knowledge=_render_knowledge(knowledge_cards),
    )
    return system, user


def draft_output_schema() -> dict:
    """Return the JSON schema supplied to providers that support it."""

    return DraftOutput.model_json_schema()


@cache
def _read_prompt(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _render_rule_hits(face_id: str, rule_hits: list[RuleHit]) -> str:
    if not rule_hits:
        return "- (none detected)"

    descriptions = load_rule_pack(face_id).descriptions
    lines = []
    for hit in rule_hits:
        desc = descriptions.get(hit.rule_id, hit.message_key)
        lines.append(
            f"- {hit.rule_id} | family={hit.family} | severity={hit.severity}: {desc}"
        )
    return "\n".join(lines)


def _render_signals(signals: list[Signal]) -> str:
    if not signals:
        return "[]"
    payload = [signal.model_dump(exclude_none=True) for signal in signals]
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _render_knowledge(cards: Sequence[KnowledgeCard]) -> str:
    if not cards:
        return "- (none selected)"
    if len(cards) > 3:
        raise ValueError("At most three knowledge cards may enter the answer prompt")

    blocks = []
    for card in cards:
        blocks.append(
            "\n".join(
                [
                    f"- CARD {card.id} version={card.version}",
                    f"  mechanism: {card.mechanism}",
                    f"  possible warning signs: {json.dumps(card.red_flags, ensure_ascii=False)}",
                    f"  verification guidance: {json.dumps(card.verify_steps, ensure_ascii=False)}",
                    f"  questions: {json.dumps(card.questions, ensure_ascii=False)}",
                    "  Treat this as reviewed guidance, never as proof that the current "
                    "person or situation matches a previous case.",
                ]
            )
        )
    return "\n".join(blocks)
