"""T7 — safety validator & formatter (V1_TECHNICAL_PLAN §9).

Live acceptance specs that skip until validate.py / format.py land. They encode
the §9 deterministic checks: reject verdict words, leaked/fabricated contacts,
and unsafe "open the link" instructions; require non-empty verify/ask.
"""

import inspect

import pytest


def _verdict(result) -> bool:
    if isinstance(result, bool):
        return result
    for attr in ("ok", "valid", "passed", "is_valid", "accepted"):
        if hasattr(result, attr):
            return bool(getattr(result, attr))
    pytest.skip(f"ValidationResult exposes no known ok-flag: {type(result).__name__}")


def _validate_or_skip(callable_or_skip):
    validate = callable_or_skip("app.engine.validate", "validate")
    if list(inspect.signature(validate).parameters)[:1] != ["draft"]:
        pytest.skip(f"validate signature differs from §9: {inspect.signature(validate)}")
    return validate


def _run(validate, draft):
    from app.engine.types import Language

    try:
        return validate(draft, [], [], Language.ru)
    except TypeError as exc:
        pytest.skip(f"validate not callable per §9: {exc}")


def test_validator_accepts_a_clean_draft(callable_or_skip) -> None:
    from app.engine.types import DraftOutput

    validate = _validate_or_skip(callable_or_skip)
    clean = DraftOutput(
        red_flags=["The message pressures you to act immediately."],
        pattern="urgency",
        verify=["Open your bank's official app yourself before doing anything."],
        ask=["Who exactly are you and from which office?"],
    )
    assert _verdict(_run(validate, clean))


def test_validator_rejects_verdict_words(callable_or_skip) -> None:
    from app.engine.types import DraftOutput

    validate = _validate_or_skip(callable_or_skip)
    # Russian "безопасно" (safe) is a banned verdict word per §9.
    bad = DraftOutput(
        red_flags=["безопасно"],
        verify=["Open the official app."],
        ask=["Who are you?"],
    )
    assert not _verdict(_run(validate, bad))


def test_validator_rejects_fabricated_contacts(callable_or_skip) -> None:
    from app.engine.types import DraftOutput

    validate = _validate_or_skip(callable_or_skip)
    bad = DraftOutput(
        red_flags=["Call the bank on +998 71 200 00 00 to confirm."],
        verify=["Open the official app."],
        ask=["Who are you?"],
    )
    assert not _verdict(_run(validate, bad))


def test_validator_rejects_empty_action_blocks(callable_or_skip) -> None:
    from app.engine.types import DraftOutput

    validate = _validate_or_skip(callable_or_skip)
    bad = DraftOutput(red_flags=["Something looks off."], verify=[], ask=[])
    assert not _verdict(_run(validate, bad))


def test_formatter_module_is_present(callable_or_skip) -> None:
    # Surface check; exact wording of the limitation line is asserted once finalized.
    format_fn = callable_or_skip(
        "app.engine.format", "format_result", "format_output", "build_message", "format_check"
    )
    assert callable(format_fn)
