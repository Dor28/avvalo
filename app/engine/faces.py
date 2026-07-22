"""Registry for the single active Avvalo check surface.

The internal ``family`` identifier is retained for database and rule-ID
compatibility even though it now represents the whole consumer product.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Face:
    """Configuration for the active consumer checking flow.

    Asset paths are decoupled from ``id`` on purpose: the ``family`` identifier
    is frozen for database and rule-ID compatibility, while the files it points
    at are named for what they are. ``knowledge_subdir`` is a bare directory
    name rather than a repo-relative path so ``FileKnowledgeStore`` keeps its
    injectable root.
    """

    id: str
    rule_pack_dir: str
    prompt_template: str
    knowledge_subdir: str
    daily_limit: int


FACES: dict[str, Face] = {
    "family": Face(
        id="family",
        rule_pack_dir="rules/checker",
        prompt_template="prompts/checker.txt",
        knowledge_subdir="checker",
        daily_limit=5,
    ),
}
