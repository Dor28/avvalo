"""Versioned YAML knowledge-card loader."""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from app.engine.knowledge.types import KnowledgeBase, KnowledgeCard, KnowledgeLookupError

_REPO_ROOT = Path(__file__).resolve().parents[3]
_KNOWLEDGE_ROOT = _REPO_ROOT / "knowledge"
_CARDS_DIRNAME = "cards"
_ID_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,79}$")
_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")


class FileKnowledgeStore:
    """Load schema-valid approved cards from the repository knowledge pack."""

    def __init__(self, root: Path = _KNOWLEDGE_ROOT) -> None:
        self.root = root

    def load(self) -> KnowledgeBase:
        return _load_knowledge_base(self.root.resolve())


@cache
def _load_knowledge_base(root: Path) -> KnowledgeBase:
    try:
        version_data = _read_yaml(root / "version.yaml")
        version = version_data.get("version")
        if not isinstance(version, str) or not _VERSION_RE.fullmatch(version):
            raise KnowledgeLookupError("knowledge/version.yaml has an invalid version")

        cards_dir = root / _CARDS_DIRNAME
        if not cards_dir.is_dir():
            raise KnowledgeLookupError("knowledge/cards directory is missing")

        cards: list[KnowledgeCard] = []
        seen_ids: set[str] = set()
        paths = sorted([*cards_dir.glob("*.yaml"), *cards_dir.glob("*.yml")])
        for path in paths:
            data = _read_yaml(path)
            raw_cards = data.get("cards")
            if not isinstance(raw_cards, list):
                raise KnowledgeLookupError(f"{path} must contain a cards list")
            for raw_card in raw_cards:
                try:
                    card = KnowledgeCard.model_validate(raw_card)
                except ValidationError as exc:
                    raise KnowledgeLookupError(f"invalid knowledge card in {path}") from exc
                _validate_card(card, seen_ids=seen_ids)
                if card.status == "approved":
                    cards.append(card)

        return KnowledgeBase(version=version, cards=tuple(cards))
    except KnowledgeLookupError:
        raise
    except (OSError, yaml.YAMLError) as exc:
        raise KnowledgeLookupError("knowledge files could not be loaded") from exc


def clear_knowledge_cache() -> None:
    """Clear the file cache for tests and operator-controlled card updates."""

    _load_knowledge_base.cache_clear()


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise KnowledgeLookupError(f"knowledge file is missing: {path.name}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise KnowledgeLookupError(f"knowledge file must be a mapping: {path.name}")
    return data


def _validate_card(card: KnowledgeCard, *, seen_ids: set[str]) -> None:
    if not _ID_RE.fullmatch(card.id):
        raise KnowledgeLookupError(f"invalid knowledge card id: {card.id}")
    if card.id in seen_ids:
        raise KnowledgeLookupError(f"duplicate knowledge card id: {card.id}")
    seen_ids.add(card.id)
    if not _VERSION_RE.fullmatch(card.version):
        raise KnowledgeLookupError(f"knowledge card {card.id} has an invalid version")
    if not card.reviewer.strip():
        raise KnowledgeLookupError(f"knowledge card {card.id} has no reviewer")
    if not card.mechanism.strip() or not card.verify_steps or not card.questions:
        raise KnowledgeLookupError(f"knowledge card {card.id} is incomplete")
    for identifier in [*card.trigger_rule_ids, *card.reviewed_case_ids]:
        if not _ID_RE.fullmatch(identifier):
            raise KnowledgeLookupError(f"knowledge card {card.id} has an invalid linked id")
