"""Face registry (§5.1).

A face selects which rule pack and prompt template a check uses and the daily
limit that applies. Everything else in the pipeline is shared between faces.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Face:
    """A product face (family or merchants)."""

    id: str
    rule_pack_dir: str
    prompt_template: str
    daily_limit: int


FACES: dict[str, Face] = {
    "family": Face(
        id="family",
        rule_pack_dir="rules/family",
        prompt_template="prompts/family.txt",
        daily_limit=5,
    ),
    "merchants": Face(
        id="merchants",
        rule_pack_dir="rules/merchants",
        prompt_template="prompts/merchants.txt",
        daily_limit=20,
    ),
}
