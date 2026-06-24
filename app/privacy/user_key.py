"""Pseudonymous user-key derivation (§5.2).

``user_key = HMAC_SHA256(secret=APP_HMAC_SECRET, msg=str(telegram_user_id))[:32]``

The raw Telegram id is never stored or logged. The key is deterministic for a
given secret, so rotating ``APP_HMAC_SECRET`` intentionally changes every key.
"""

import hashlib
import hmac

KEY_LENGTH = 32


def derive_user_key(telegram_user_id: int | str, *, secret: str) -> str:
    """Return the 32-char hex pseudonymous key for a Telegram user id."""

    digest = hmac.new(
        secret.encode("utf-8"),
        str(telegram_user_id).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest[:KEY_LENGTH]
