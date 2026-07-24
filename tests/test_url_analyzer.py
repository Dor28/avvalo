"""One URL analyzer: shape classification, normalization, and the no-fetch rule.

Roadmap Phase 1.2. Rule matching, minimization, and reputation lookup all resolve
a submitted link through ``app.engine.url``; these tests pin the shapes that
analyzer must recognize and prove the three callers cannot drift apart.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
import yaml

from app.engine.minimize import minimize
from app.engine.rules import classify_link as rules_classify_link
from app.engine.rules import run_rules
from app.engine.url import (
    _BASELINE_BRANDS,
    OFFICIAL_DOMAINS_PATH,
    URL_RE,
    classify_link,
    describe_link,
    extract_normalized_domains,
    load_official_domains,
    normalize_domain,
)
from app.engine.url_reputation import normalize_domain as reputation_normalize_domain

REPO_ROOT = Path(__file__).resolve().parents[1]

# Cyrillic homographs are spelled with escapes so the intent is unambiguous in
# source: "click" with a Cyrillic es, and its punycode encoding.
CYRILLIC_CLICK = "\u0441lick.uz"
PUNYCODE_CLICK = "xn--lick-k6d.uz"


@pytest.mark.parametrize(
    ("raw_url", "expected"),
    [
        # Genuine destinations stay unlabeled, including subdomains of a real one.
        ("https://payme.uz/pay", None),
        ("https://my.click.uz/account", None),
        ("https://www.uzum.uz", None),
        ("https://t.me/some_channel", None),
        ("https://example.com/page", None),
        # Shorteners hide the destination.
        ("https://bit.ly/3xYz", "shortened"),
        ("https://clck.ru/abc", "shortened"),
        # Brand imitation, including defanged and one-edit spellings.
        ("https://payme-secure.example", "lookalike-domain"),
        ("hxxps://payme-secure[.]example/a", "lookalike-domain"),
        ("https://click-uz.example/pay", "lookalike-domain"),
        # Punycode and mixed-script imitation of a catalog brand.
        (f"https://{CYRILLIC_CLICK}/pay", "lookalike-domain"),
        (f"https://{PUNYCODE_CLICK}/pay", "lookalike-domain"),
        # userinfo@ hides the real host behind a trusted-looking prefix.
        ("https://click.uz@evil.example/login", "credentials-in-url"),
        ("https://uzum.uz:pass@evil.example", "credentials-in-url"),
        # Bare IP hosts.
        ("http://185.23.44.9/pay", "ip-address"),
        ("http://[2001:db8::1]/pay", "ip-address"),
        # A public suffix used as an interior label.
        ("https://sberbank.uz.secure-login.example", "domain-in-subdomain"),
        ("https://account.com.verify-now.example", "domain-in-subdomain"),
    ],
)
def test_classify_link_labels_each_deceptive_shape(raw_url: str, expected: str | None) -> None:
    assert classify_link(raw_url) == expected


@pytest.mark.parametrize(
    ("raw_url", "expected"),
    [
        ("https://www.Click.UZ/pay", "click.uz"),
        ("hxxps://payme-secure[.]example/a", "payme-secure.example"),
        ("click.uz", "click.uz"),
        ("https://click.uz@evil.example/login", "evil.example"),
        (f"https://{PUNYCODE_CLICK}/pay", CYRILLIC_CLICK),
    ],
)
def test_normalize_domain_resolves_to_one_exact_form(raw_url: str, expected: str) -> None:
    assert normalize_domain(raw_url) == expected


def test_punycode_and_unicode_spellings_normalize_together() -> None:
    """The reputation store must not miss a domain because of its encoding."""

    assert normalize_domain(f"https://{PUNYCODE_CLICK}") == normalize_domain(
        f"https://{CYRILLIC_CLICK}"
    )


@pytest.mark.parametrize(
    "raw_url",
    ["https://", "https://:8080/path", "http://[not-ipv6/pay", "https://example.com:notaport"],
)
def test_malformed_authority_has_no_label_and_does_not_raise(raw_url: str) -> None:
    """A broken authority degrades to "nothing to say", never to an exception."""

    assert classify_link(raw_url) in {None, "credentials-in-url", "ip-address"}
    describe_link(raw_url)


def test_extract_normalized_domains_deduplicates_encodings() -> None:
    text = f"Birinchi https://CLICK.uz/pay, keyin www.click.uz, keyin {PUNYCODE_CLICK}"
    assert extract_normalized_domains(text) == ("click.uz", CYRILLIC_CLICK)


# --- the three callers resolve one link the same way -------------------------


def test_rules_minimize_and_reputation_share_one_analyzer() -> None:
    """A homograph must not be a lookalike to one stage and invisible to another."""

    raw_text = f"To'lov: https://{CYRILLIC_CLICK}/pay"

    _hits, signals = run_rules(raw_text)
    minimized = minimize(raw_text, signals)

    assert ("link_lookalike", "lookalike-domain") in {(s.kind, s.note) for s in signals}
    assert "[LINK: lookalike-domain]" in minimized
    assert reputation_normalize_domain(f"https://{CYRILLIC_CLICK}") == CYRILLIC_CLICK
    assert CYRILLIC_CLICK not in minimized


def test_rules_package_reexports_the_shared_classifier() -> None:
    assert rules_classify_link is classify_link


def test_submitted_content_stages_define_no_second_url_pattern() -> None:
    """Guard the unification: a second host pattern is how these drifted before.

    Scoped to the three stages that analyze *submitted* content. `validate.py`
    (scans model output) and `url_reputation/refresh.py` (parses operator feed
    files) legitimately keep their own patterns for a different corpus.
    """

    stages = [
        "app/engine/minimize.py",
        "app/engine/rules/engine.py",
        "app/engine/url_reputation/normalize.py",
    ]
    offenders = [
        stage
        for stage in stages
        # The bare-host branch of a general URL pattern; `minimize` keeps a
        # narrow scheme-anchored t.me rule, which is not a host matcher.
        if r"(?:www\.)?" in (REPO_ROOT / stage).read_text(encoding="utf-8")
    ]
    assert offenders == [], (
        f"these stages match hosts themselves instead of importing "
        f"app.engine.url.URL_RE: {offenders}"
    )


@pytest.mark.parametrize(
    "raw_url",
    [
        "https://click.uz@evil.example/login",
        f"https://{PUNYCODE_CLICK}/pay",
        "http://185.23.44.9/pay",
    ],
)
def test_analysis_never_fetches_the_destination(raw_url: str) -> None:
    """No code path may open a submitted destination — shape analysis only."""

    classify_link(raw_url)
    normalize_domain(raw_url)

    source = inspect.getsource(__import__("app.engine.url", fromlist=["url"]))
    for forbidden in ("requests", "httpx", "urlopen", "socket", "getaddrinfo", "aiohttp"):
        assert forbidden not in source, f"URL analyzer must not reach the network: {forbidden}"


# --- the reviewed catalog ----------------------------------------------------


def test_catalog_yaml_is_a_superset_of_the_in_code_floor() -> None:
    """The founder extends the catalog in YAML; the floor may never drift above it."""

    catalog = load_official_domains()
    for brand, domains in _BASELINE_BRANDS.items():
        assert brand in catalog.brands, f"{brand} disappeared from {OFFICIAL_DOMAINS_PATH.name}"
        assert set(domains) <= set(catalog.brands[brand]), (
            f"{brand} lost a reviewed domain from the shipped floor"
        )


def test_catalog_entries_are_usable() -> None:
    """A brand token shorter than 4 chars or a bad domain would misfire on real text."""

    raw = yaml.safe_load(OFFICIAL_DOMAINS_PATH.read_text(encoding="utf-8"))
    assert raw["version"], "catalog must carry a version for operator review"

    for entry in raw["brands"]:
        brand = entry["brand"]
        assert brand == brand.casefold().strip(), f"{brand} must be lowercase and trimmed"
        # Under three characters a brand token matches ordinary words; at three
        # it matches by exact substring only (see `_looks_like_brand`).
        assert len(brand) >= 3, f"{brand} is too short and would match ordinary words"
        assert entry["domains"], f"{brand} has no real domain and would flag its own site"
        for domain in entry["domains"]:
            assert normalize_domain(domain) == domain, f"{domain} is not in normalized form"


def test_every_catalog_domain_is_treated_as_genuine() -> None:
    """The catalog's own domains must never be labeled as imitations of themselves."""

    for brand, domains in load_official_domains().brands.items():
        for domain in domains:
            assert classify_link(f"https://{domain}/") is None, (
                f"{domain} ({brand}) is a reviewed official domain but was labeled"
            )


def test_shortener_list_is_normalized() -> None:
    for shortener in load_official_domains().shorteners:
        assert normalize_domain(shortener) == shortener


def test_url_regex_finds_defanged_and_non_ascii_hosts() -> None:
    text = f"hxxps://payme-secure[.]example/a va {CYRILLIC_CLICK} va https://click.uz"
    assert len(URL_RE.findall(text)) == 3
