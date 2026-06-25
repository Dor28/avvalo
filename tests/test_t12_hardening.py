"""T12 — hardening: timeouts & graceful failure (V1_TECHNICAL_PLAN §14, §13 T12).

The timeout status is part of the locked type contract (live); the actual
asyncio.wait_for wrapping is a spec that skips until the helper lands.
"""


def test_timeout_status_is_part_of_the_contract() -> None:
    from app.engine.types import CheckStatus

    # §14: on timeout the pipeline returns CheckStatus.timeout (no safety conclusion).
    assert CheckStatus.timeout.value == "timeout"


def test_pipeline_has_a_timeout_wrapper(callable_or_skip) -> None:
    wrapper = callable_or_skip(
        "app.engine.pipeline",
        "_with_timeout",
        "with_timeout",
        "run_with_timeout",
        "_guard_timeout",
    )
    assert callable(wrapper)
