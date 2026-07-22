"""Ephemeral URL/domain normalization and hashing for local exact lookup.

Raw submitted links are handled only inside the process and never persisted,
logged, or sent to a per-check reputation API.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from urllib.parse import urlparse

_URL_RE = re.compile(
    r"(?ix)"
    r"\b(?:https?|hxxps?)://[^\s<>()]+"
    r"|\b(?:www\.)?[a-z0-9\u0080-\uffff][a-z0-9\u0080-\uffff.-]*"
    r"(?:\.|\[\.\]|\(\.\))[a-z\u0080-\uffff]{2,}(?:/[^\s<>()]*)?"
)


def extract_normalized_domains(text: str) -> tuple[str, ...]:
    """Return unique normalized domains found in ephemeral raw text."""

    domains = (
        normalize_domain(match.group(0))
        for match in _URL_RE.finditer(text)
    )
    return tuple(dict.fromkeys(domain for domain in domains if domain))


def normalize_domain(value: str) -> str | None:
    """Normalize scheme/www/case/IDNA variants to one exact-match domain."""

    cleaned = value.strip().strip(".,;:!?)]}\"'")
    cleaned = cleaned.replace("[.]", ".").replace("(.)", ".")
    cleaned = re.sub(r"(?i)^hxxp", "http", cleaned)
    if "://" not in cleaned:
        cleaned = f"https://{cleaned}"
    parsed = urlparse(cleaned)
    domain = (parsed.hostname or "").strip(".").casefold()
    if domain.startswith("www."):
        domain = domain.removeprefix("www.")
    if not domain:
        return None
    try:
        decoded_domain = domain.encode("ascii").decode("idna")
    except UnicodeError:
        decoded_domain = domain
    domain = decoded_domain
    return unicodedata.normalize("NFKC", domain).casefold().strip(".") or None


def hash_domain(domain: str) -> str:
    """Hash one normalized domain as lowercase SHA-256 hex."""

    return hashlib.sha256(domain.encode("utf-8")).hexdigest()
