"""Sentry initialization for the error-log stream.

Strictly opt-in and minimal: no default integrations, no local-variable
capture, no automatic exception/request capture. With every auto-instrumented
integration disabled, Sentry cannot independently observe the app — it only
ever receives what :func:`app.obs.events.log_error` explicitly sends it, the
same allowlisted, content-scrubbed fields that go to the local error log.
"""

import sentry_sdk

from app.config import Settings


def init_sentry(settings: Settings) -> None:
    """Initialize Sentry if ``SENTRY_DSN`` is configured; a no-op otherwise."""

    if settings.sentry_dsn is None:
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn.get_secret_value(),
        environment=settings.sentry_environment,
        default_integrations=False,
        integrations=[],
        send_default_pii=False,
        include_local_variables=False,
    )
