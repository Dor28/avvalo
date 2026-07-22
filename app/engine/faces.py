"""Registry for the single active Avvalo check surface.

The internal ``family`` identifier is retained for database and rule-ID
compatibility even though it now represents the whole consumer product.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Face:
    """Configuration for the active consumer checking flow."""

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
}
