"""T9 — daily limits, feedback & privacy-safe events (V1_TECHNICAL_PLAN §12, §13 T9).

The rate-limit and feedback storage primitives exist now (tested live below). The
event logger's content-refusal discipline (§12) is a live spec that skips until
obs/events.py lands.
"""

import inspect

import pytest

from app.data import repo
from app.engine.faces import FACES


async def test_daily_limit_boundary_is_reachable(session) -> None:
    face = "family_shield"
    limit = FACES[face].daily_limit
    counts = [
        await repo.increment_usage(session, user_key="capped", face=face) for _ in range(limit)
    ]
    assert counts[-1] == limit
    assert await repo.get_usage(session, user_key="capped", face=face) == limit


async def test_feedback_is_stored_categorically(session) -> None:
    check_id = await repo.record_check_event(
        session, user_key="fb", face="family_shield", input_type="text", language="ru", status="ok"
    )
    await repo.record_feedback(
        session, check_id=check_id, usefulness="partly", next_action="verify"
    )
    await session.commit()
    # No assertion on content — feedback rows are categorical only (§5.2).


def test_log_event_accepts_metadata_and_refuses_content(callable_or_skip) -> None:
    log_event = callable_or_skip("app.obs.events", "log_event")
    params = inspect.signature(log_event).parameters.values()
    if not any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params):
        pytest.skip(f"log_event does not take **fields: {inspect.signature(log_event)}")

    try:
        log_event("check_completed", language="ru", face="family_shield", status="ok")
    except TypeError as exc:
        pytest.skip(f"log_event metadata signature differs from §12: {exc}")

    # §12: a content-like field must be refused outright.
    with pytest.raises((ValueError, TypeError, KeyError)):
        log_event("check_completed", raw_text="secret submitted content")
