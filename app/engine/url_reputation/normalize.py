"""Domain hashing for local exact lookup, over the shared URL analyzer.

Normalization itself lives in :mod:`app.engine.url` so the reputation lookup can
never disagree with rule matching or minimization about what a submitted link
points to. Raw links are handled only inside the process and are never
persisted, logged, or sent to a per-check reputation API.
"""

from __future__ import annotations

import hashlib

from app.engine.url import extract_normalized_domains, normalize_domain

__all__ = ["extract_normalized_domains", "hash_domain", "normalize_domain"]


def hash_domain(domain: str) -> str:
    """Hash one normalized domain as lowercase SHA-256 hex."""

    return hashlib.sha256(domain.encode("utf-8")).hexdigest()
