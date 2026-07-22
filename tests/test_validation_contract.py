"""Direct contracts for deterministic safety validation and result formatting."""

from app.engine.format import format_result
from app.engine.types import DraftOutput, Language
from app.engine.validate import validate


def _run(draft: DraftOutput):
    return validate(draft, signals=[], rule_hits=[], language=Language.ru)


def test_validator_accepts_a_clean_draft() -> None:
    clean = DraftOutput(
        red_flags=["The message pressures you to act immediately."],
        pattern="urgency",
        verify=["Open your bank's official app yourself before doing anything."],
        ask=["Who exactly are you and from which office?"],
    )
    result = _run(clean)

    assert result.ok is True
    assert result.reason is None


def test_validator_rejects_verdict_words() -> None:
    bad = DraftOutput(
        red_flags=["безопасно"],
        verify=["Open the official app."],
        ask=["Who are you?"],
    )
    result = _run(bad)

    assert result.ok is False
    assert result.reason is not None and "banned verdict word" in result.reason


def test_validator_rejects_fabricated_contacts() -> None:
    bad = DraftOutput(
        red_flags=["Call the bank on +998 71 200 00 00 to confirm."],
        verify=["Open the official app."],
        ask=["Who are you?"],
    )
    result = _run(bad)

    assert result.ok is False
    assert result.reason == "raw phone number leaked"


def test_validator_rejects_empty_action_blocks() -> None:
    bad = DraftOutput(red_flags=["Something looks off."], verify=[], ask=[])
    result = _run(bad)

    assert result.ok is False
    assert result.reason == "verify block is empty"


def test_formatter_renders_current_sections_in_each_reply_language() -> None:
    draft = DraftOutput(
        red_flags=["One detail deserves attention."],
        verify=["Check it through an independent official channel."],
        ask=["Which source can confirm this claim?"],
    )

    assert "Nimani tekshiring" in format_result(draft, Language.uz_latn)
    assert "Что проверить" in format_result(draft, Language.ru)
