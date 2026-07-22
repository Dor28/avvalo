"""Consent-version helpers and the consent gate (§12).

A user may process content only when a consent row exists for ``user_key`` at
the current ``NOTICE_VERSION``. Bumping the notice version forces re-consent
because the stored version no longer matches.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.data import repo
from app.data.models import Consent


def is_consent_current(consent: Consent | None, notice_version: str) -> bool:
    """True when *consent* exists and matches the current notice version."""

    return consent is not None and consent.notice_version == notice_version


async def grant_consent(
    session: AsyncSession,
    *,
    user_key: str,
    language: str,
    notice_version: str,
) -> Consent:
    """Record (or refresh) consent for ``user_key`` at *notice_version*."""

    return await repo.upsert_consent(
        session,
        user_key=user_key,
        notice_version=notice_version,
        language=language,
    )
