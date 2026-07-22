"""Versioned YAML knowledge-card loader."""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from app.engine.faces import FACES
from app.engine.knowledge.types import KnowledgeBase, KnowledgeCard, KnowledgeLookupError

_REPO_ROOT = Path(__file__).resolve().parents[3]
_KNOWLEDGE_ROOT = _REPO_ROOT / "knowledge"
_ID_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,79}$")
_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")


# Merged YAML+database bases currently in force, keyed by face ID. Empty until
# the first refresh succeeds; see ``FileKnowledgeStore.load``.
_ACTIVE_BASES: dict[str, KnowledgeBase] = {}


class FileKnowledgeStore:
    """Load schema-valid approved cards from the repository knowledge pack."""

    def __init__(self, root: Path = _KNOWLEDGE_ROOT) -> None:
        self.root = root

    def load(self, face_id: str) -> KnowledgeBase:
        """Return the base in force for ``face_id``.

        Synchronous by contract: ``KnowledgeStore`` is a sync Protocol with
        three call sites, so a merged base is served from a process-level
        snapshot rather than queried. ``app.knowledge_store.apply`` swaps that
        snapshot in on a schedule and after an operator edit. Before the first
        successful refresh — and whenever the database is unreachable — this
        falls back to the YAML pack shipped in the image, so knowledge degrades
        to the baseline instead of to nothing.

        A store built on a non-default root is a tool/test affordance and always
        reads the files under that root.
        """

        root = self.root.resolve()
        if root == _KNOWLEDGE_ROOT.resolve():
            active = _ACTIVE_BASES.get(face_id)
            if active is not None:
                return active
        return _load_knowledge_base(root, face_id)


def load_yaml_knowledge_base(face_id: str) -> KnowledgeBase:
    """Load the shipped baseline for ``face_id``, ignoring any published snapshot."""

    return _load_knowledge_base(_KNOWLEDGE_ROOT.resolve(), face_id)


def set_active_knowledge_base(face_id: str, base: KnowledgeBase) -> None:
    """Publish a merged base as the one in force for ``face_id``."""

    _ACTIVE_BASES[face_id] = base


def clear_active_knowledge_bases() -> None:
    """Drop every merged base, reverting to the shipped YAML baseline."""

    _ACTIVE_BASES.clear()


@cache
def _load_knowledge_base(root: Path, face_id: str) -> KnowledgeBase:
    if face_id not in FACES:
        raise KnowledgeLookupError(f"unknown knowledge face: {face_id}")
    try:
        version_data = _read_yaml(root / "version.yaml")
        version = version_data.get("version")
        if not isinstance(version, str) or not _VERSION_RE.fullmatch(version):
            raise KnowledgeLookupError("knowledge/version.yaml has an invalid version")

        face_dir = root / FACES[face_id].knowledge_subdir
        if not face_dir.is_dir():
            raise KnowledgeLookupError(f"knowledge directory is missing for face: {face_id}")

        cards: list[KnowledgeCard] = []
        seen_ids: set[str] = set()
        paths = sorted([*face_dir.glob("*.yaml"), *face_dir.glob("*.yml")])
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
                _validate_card(card, expected_face=face_id, seen_ids=seen_ids)
                if card.status == "approved":
                    cards.append(card)

        return KnowledgeBase(version=version, face=face_id, cards=tuple(cards))
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


def _validate_card(card: KnowledgeCard, *, expected_face: str, seen_ids: set[str]) -> None:
    if not _ID_RE.fullmatch(card.id):
        raise KnowledgeLookupError(f"invalid knowledge card id: {card.id}")
    if card.id in seen_ids:
        raise KnowledgeLookupError(f"duplicate knowledge card id: {card.id}")
    seen_ids.add(card.id)
    if card.face != expected_face:
        raise KnowledgeLookupError(f"knowledge card {card.id} has the wrong face")
    if not _VERSION_RE.fullmatch(card.version):
        raise KnowledgeLookupError(f"knowledge card {card.id} has an invalid version")
    if not card.reviewer.strip():
        raise KnowledgeLookupError(f"knowledge card {card.id} has no reviewer")
    if not card.mechanism.strip() or not card.verify_steps or not card.questions:
        raise KnowledgeLookupError(f"knowledge card {card.id} is incomplete")
    for identifier in [*card.trigger_rule_ids, *card.reviewed_case_ids]:
        if not _ID_RE.fullmatch(identifier):
            raise KnowledgeLookupError(f"knowledge card {card.id} has an invalid linked id")
