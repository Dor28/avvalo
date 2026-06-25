"""Prompt assembly for Avvalo LLM calls."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

from app.engine.faces import FACES
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
