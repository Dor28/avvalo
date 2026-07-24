"""One URL analyzer shared by rule matching, minimization, and reputation lookup.

Technical plan §5.1 (deterministic rules) and §9 (minimization). Every stage that
looks at a submitted link resolves it here, so a destination cannot be read one
way by the structural-signal extractor and another way by the reputation lookup.

Analysis is by **shape only**. Nothing in this module opens, fetches, renders, or
resolves a submitted destination, and no result claims an official source was
checked.
"""

from __future__ import annotations

import contextlib
import ipaddress
import logging
import re
import unicodedata
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from urllib.parse import urlsplit

import yaml

_LOG = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
OFFICIAL_DOMAINS_PATH = _REPO_ROOT / "rules" / "shared" / "official_domains.yaml"

# Unicode-aware: a lookalike host may be written in Cyrillic or arrive already
# percent/IDNA encoded, so the host character class must reach beyond ASCII.
URL_RE = re.compile(
    r"(?ix)"
    r"\b(?:https?|hxxps?)://[^\s<>()]+"
    r"|\b(?:www\.)?[a-z0-9\u0080-\uffff][a-z0-9\u0080-\uffff.-]*"
    r"(?:\.|\[\.\]|\(\.\))[a-z\u0080-\uffff]{2,}(?:/[^\s<>()]*)?"
)

_TRAILING_PUNCTUATION = ".,;:!?)]}\"'"

# Labels attached to a link. They are opaque tokens for the prompt and the
# minimizer (``[LINK: <label>]``) — deliberately descriptive of the *shape*, never
# of intent, and never a verdict.
LABEL_SHORTENED = "shortened"
LABEL_LOOKALIKE = "lookalike-domain"
LABEL_DOMAIN_IN_SUBDOMAIN = "domain-in-subdomain"
LABEL_MIXED_SCRIPT = "mixed-script-domain"
LABEL_CREDENTIALS = "credentials-in-url"
LABEL_IP = "ip-address"

# Confusable folding: the Cyrillic and Greek letters that render like Latin ones
# in a domain. Written as escapes so the table stays readable and ruff's
# ambiguous-character rule (RUF001) has nothing to flag.
_CONFUSABLE_TO_ASCII = {
    "\u0430": "a",  # CYRILLIC SMALL LETTER A
    "\u0432": "b",  # CYRILLIC SMALL LETTER VE
    "\u0435": "e",  # CYRILLIC SMALL LETTER IE
    "\u0451": "e",  # CYRILLIC SMALL LETTER IO
    "\u043a": "k",  # CYRILLIC SMALL LETTER KA
    "\u043c": "m",  # CYRILLIC SMALL LETTER EM
    "\u043d": "h",  # CYRILLIC SMALL LETTER EN
    "\u043e": "o",  # CYRILLIC SMALL LETTER O
    "\u0440": "p",  # CYRILLIC SMALL LETTER ER
    "\u0441": "c",  # CYRILLIC SMALL LETTER ES
    "\u0442": "t",  # CYRILLIC SMALL LETTER TE
    "\u0443": "y",  # CYRILLIC SMALL LETTER U
    "\u0445": "x",  # CYRILLIC SMALL LETTER HA
    "\u0456": "i",  # CYRILLIC SMALL LETTER BYELORUSSIAN-UKRAINIAN I
    "\u0458": "j",  # CYRILLIC SMALL LETTER JE
    "\u0455": "s",  # CYRILLIC SMALL LETTER DZE
    "\u0501": "d",  # CYRILLIC SMALL LETTER KOMI DE
    "\u04bb": "h",  # CYRILLIC SMALL LETTER SHHA
    "\u051b": "q",  # CYRILLIC SMALL LETTER QA
    "\u051d": "w",  # CYRILLIC SMALL LETTER WE
    "\u03b1": "a",  # GREEK SMALL LETTER ALPHA
    "\u03b5": "e",  # GREEK SMALL LETTER EPSILON
    "\u03b9": "i",  # GREEK SMALL LETTER IOTA
    "\u03ba": "k",  # GREEK SMALL LETTER KAPPA
    "\u03bd": "v",  # GREEK SMALL LETTER NU
    "\u03bf": "o",  # GREEK SMALL LETTER OMICRON
    "\u03c1": "p",  # GREEK SMALL LETTER RHO
    "\u03c4": "t",  # GREEK SMALL LETTER TAU
    "\u03c5": "u",  # GREEK SMALL LETTER UPSILON
    "\u03c7": "x",  # GREEK SMALL LETTER CHI
}
_CONFUSABLE_TABLE = str.maketrans(_CONFUSABLE_TO_ASCII)

# Detection must never collapse to "no lookalikes" because a data file failed to
# parse. This mirrors ``load_rule_pack()``: degrade to the shipped floor, never to
# nothing. ``tests/test_url_analyzer.py`` asserts the YAML is a superset, so the
# catalog can grow in data without this floor drifting behind it.
_BASELINE_BRANDS: dict[str, tuple[str, ...]] = {
    "agrobank": ("agrobank.uz",),
    "anorbank": ("anorbank.uz",),
    "beeline": ("beeline.uz",),
    "click": ("click.uz",),
    "hamkorbank": ("hamkorbank.uz",),
    "humo": ("humocard.uz", "humo.uz"),
    "ipoteka": ("ipotekabank.uz",),
    "kapitalbank": ("kapitalbank.uz",),
    "olx": ("olx.uz",),
    "payme": ("payme.uz",),
    "telegram": ("telegram.org", "t.me"),
    "uzcard": ("uzcard.uz",),
    "uzum": ("uzum.uz", "uzumbank.uz"),
    "xalqqbank": ("xb.uz",),
}
_BASELINE_SHORTENERS = frozenset(
    {
        "bit.ly",
        "clck.ru",
        "cutt.ly",
        "goo.gl",
        "is.gd",
        "lnkd.in",
        "ow.ly",
        "s.id",
        "shorturl.at",
        "t.co",
        "tiny.cc",
        "tinyurl.com",
    }
)
_BASELINE_NESTED_SUFFIXES = frozenset({"uz", "com", "net", "org", "ru"})


@dataclass(frozen=True)
class OfficialDomainCatalog:
    """Founder-reviewed URL-shape reference data."""

    brands: dict[str, tuple[str, ...]]
    shorteners: frozenset[str]
    nested_suffixes: frozenset[str]


@dataclass(frozen=True)
class LinkShape:
    """What a submitted link looks like, with nothing fetched to find out."""

    domain: str | None
    has_userinfo: bool
    is_ip: bool
    mixed_script: bool


@cache
def load_official_domains() -> OfficialDomainCatalog:
    """Return the reviewed catalog, falling back to the in-code floor on failure."""

    try:
        raw = yaml.safe_load(OFFICIAL_DOMAINS_PATH.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        _LOG.error("official-domain catalog unreadable; using baseline floor")
        return _baseline_catalog()
    if not isinstance(raw, dict):
        _LOG.error("official-domain catalog malformed; using baseline floor")
        return _baseline_catalog()

    brands = dict(_BASELINE_BRANDS)
    for entry in raw.get("brands") or []:
        if not isinstance(entry, dict):
            continue
        brand = str(entry.get("brand", "")).strip().casefold()
        domains = tuple(
            normalized
            for domain in entry.get("domains") or []
            if (normalized := normalize_domain(str(domain)))
        )
        # A brand with no usable domain would flag every host containing the
        # token, including the organization's own site. Length is not filtered
        # here: short real brands exist (olx), and the fuzzy path in
        # ``_looks_like_brand`` already refuses tokens under four characters, so
        # they match by exact substring only.
        if brand and domains:
            brands[brand] = domains

    return OfficialDomainCatalog(
        brands=brands,
        shorteners=_string_set(raw.get("shorteners"), _BASELINE_SHORTENERS),
        nested_suffixes=_string_set(raw.get("nested_suffixes"), _BASELINE_NESTED_SUFFIXES),
    )


def find_urls(text: str) -> list[str]:
    """Return every raw URL-shaped span in ephemeral text, in order."""

    return [match.group(0) for match in URL_RE.finditer(text)]


def extract_normalized_domains(text: str) -> tuple[str, ...]:
    """Return unique normalized domains found in ephemeral raw text."""

    domains = (normalize_domain(raw_url) for raw_url in find_urls(text))
    return tuple(dict.fromkeys(domain for domain in domains if domain))


def normalize_domain(value: str) -> str | None:
    """Normalize scheme/www/case/IDNA variants to one exact-match domain."""

    return describe_link(value).domain


def describe_link(raw_url: str) -> LinkShape:
    """Resolve one raw link into its normalized shape without fetching it."""

    cleaned = raw_url.strip().strip(_TRAILING_PUNCTUATION)
    cleaned = cleaned.replace("[.]", ".").replace("(.)", ".")
    cleaned = re.sub(r"(?i)^hxxp", "http", cleaned)
    if "://" not in cleaned:
        cleaned = f"https://{cleaned}"

    try:
        parts = urlsplit(cleaned)
        host = parts.hostname or ""
        # ``username`` is the userinfo before "@" — the display-deception trick in
        # https://click.uz@evil.example, where the real host is evil.example.
        has_userinfo = bool(parts.username or parts.password)
    except ValueError:
        # A malformed authority (bad port, unbalanced brackets) is not a crash:
        # the link simply has no host we can reason about.
        return LinkShape(domain=None, has_userinfo=False, is_ip=False, mixed_script=False)

    domain = host.strip(".").casefold()
    if domain.startswith("www."):
        domain = domain.removeprefix("www.")
    if not domain:
        return LinkShape(domain=None, has_userinfo=has_userinfo, is_ip=False, mixed_script=False)

    # Already unicode, or punycode that does not decode? Either way the raw form
    # is the best available representation.
    with contextlib.suppress(UnicodeError):
        domain = domain.encode("ascii").decode("idna")
    domain = unicodedata.normalize("NFKC", domain).casefold().strip(".")
    if not domain:
        return LinkShape(domain=None, has_userinfo=has_userinfo, is_ip=False, mixed_script=False)

    return LinkShape(
        domain=domain,
        has_userinfo=has_userinfo,
        is_ip=_is_ip_literal(domain),
        mixed_script=len(_scripts(domain)) > 1,
    )


def classify_link(raw_url: str) -> str | None:
    """Classify a raw link into the safe shape labels used by minimization.

    At most one label is returned, most-deceptive first: a link that both hides
    its host behind userinfo and imitates a brand is reported as the userinfo
    trick, because that is the part the reader cannot see.
    """

    shape = describe_link(raw_url)
    if not shape.domain:
        return None

    catalog = load_official_domains()

    if shape.has_userinfo:
        return LABEL_CREDENTIALS
    if shape.is_ip:
        return LABEL_IP
    if shape.domain in catalog.shorteners:
        return LABEL_SHORTENED

    # Brand comparison runs on the confusable-folded host so a Cyrillic imitation
    # is measured against the Latin brand. The allowlist is checked on the
    # *unfolded* host, so a folded collision can never certify an imitation as
    # the genuine organization.
    folded = shape.domain.translate(_CONFUSABLE_TABLE)
    folded_labels = re.split(r"[^a-z0-9]+", folded)
    for brand, allowed_domains in catalog.brands.items():
        if not shape.mixed_script and _domain_is_allowed(shape.domain, allowed_domains):
            continue
        if brand in folded or any(_looks_like_brand(label, brand) for label in folded_labels):
            return LABEL_LOOKALIKE

    if _has_nested_suffix(shape.domain, catalog.nested_suffixes):
        return LABEL_DOMAIN_IN_SUBDOMAIN
    if shape.mixed_script:
        return LABEL_MIXED_SCRIPT

    return None


def _baseline_catalog() -> OfficialDomainCatalog:
    return OfficialDomainCatalog(
        brands=dict(_BASELINE_BRANDS),
        shorteners=_BASELINE_SHORTENERS,
        nested_suffixes=_BASELINE_NESTED_SUFFIXES,
    )


def _string_set(value: object, floor: frozenset[str]) -> frozenset[str]:
    if not isinstance(value, list):
        return floor
    entries = {str(item).strip().casefold() for item in value if str(item).strip()}
    return frozenset(entries | floor)


def _is_ip_literal(domain: str) -> bool:
    try:
        ipaddress.ip_address(domain.strip("[]"))
    except ValueError:
        return False
    return True


def _scripts(value: str) -> set[str]:
    """Return the writing systems present in a host, ignoring digits and marks."""

    scripts: set[str] = set()
    for char in value:
        if char in ".-_" or char.isdigit():
            continue
        code = ord(char)
        if "a" <= char <= "z":
            scripts.add("latin")
        elif 0x0400 <= code <= 0x04FF:
            scripts.add("cyrillic")
        elif 0x0370 <= code <= 0x03FF:
            scripts.add("greek")
        elif code > 0x7F:
            scripts.add("other")
    return scripts


def _has_nested_suffix(domain: str, nested_suffixes: frozenset[str]) -> bool:
    """Detect a public suffix used as an interior label (click.uz.evil.example)."""

    labels = domain.split(".")
    # The final label is the real suffix and the one before it is the registrable
    # name; only labels further left can be a disguise.
    return any(label in nested_suffixes for label in labels[:-2])


def _domain_is_allowed(domain: str, allowed_domains: tuple[str, ...]) -> bool:
    return any(domain == allowed or domain.endswith(f".{allowed}") for allowed in allowed_domains)


def _looks_like_brand(label: str, brand: str) -> bool:
    if len(brand) < 4 or abs(len(label) - len(brand)) > 2:
        return False
    if label == brand:
        return True
    return _levenshtein_at_most_one(label, brand)


def _levenshtein_at_most_one(left: str, right: str) -> bool:
    if left == right:
        return True
    if abs(len(left) - len(right)) > 1:
        return False

    edits = 0
    i = 0
    j = 0
    while i < len(left) and j < len(right):
        if left[i] == right[j]:
            i += 1
            j += 1
            continue
        edits += 1
        if edits > 1:
            return False
        if len(left) == len(right):
            i += 1
            j += 1
        elif len(left) > len(right):
            i += 1
        else:
            j += 1

    return True
