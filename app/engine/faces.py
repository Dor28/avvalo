"""Face registry (§5.1).

A face selects which rule pack and prompt template a check uses and the daily
limit that applies. Everything else in the pipeline is shared between faces.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Face:
    """A product face (Family Shield or Seller Guard)."""

    id: str
    rule_pack_dir: str
    prompt_template: str
    daily_limit: int


FACES: dict[str, Face] = {
    "family_shield": Face(
        id="family_shield",
        rule_pack_dir="rules/family_shield",
        prompt_template="prompts/family_shield.txt",
        daily_limit=5,
    ),
    "seller_guard": Face(
        id="seller_guard",
        rule_pack_dir="rules/seller_guard",
        prompt_template="prompts/seller_guard.txt",
        daily_limit=20,
    ),
}
