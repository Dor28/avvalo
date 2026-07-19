"""R6 local URL reputation check with no per-submission network call."""

from __future__ import annotations

from app.engine.types import RuleHit
from app.engine.url_reputation.normalize import extract_normalized_domains, hash_domain
from app.engine.url_reputation.types import URLReputationStore

BLOCKLIST_RULE_ID = "shared.link.blocklisted"


async def lookup_url_reputation(
    raw_text: str,
    *,
    store: URLReputationStore,
) -> list[RuleHit]:
    """Return one synthetic authoritative fact when a local hash matches."""

    hashes = tuple(hash_domain(domain) for domain in extract_normalized_domains(raw_text))
    matches = await store.lookup(hashes)
    if not matches:
        return []
    sources = sorted({match.source for match in matches})
    first_seen = min(match.first_seen for match in matches).date().isoformat()
    description = (
        "The submitted link's domain appears in a public phishing blocklist; "
        f"sources={','.join(sources)}; listed_since={first_seen}."
    )
    return [
        RuleHit(
            rule_id=BLOCKLIST_RULE_ID,
            family="suspicious_link_qr",
            message_key=description,
            severity=3,
        )
    ]
