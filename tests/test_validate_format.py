"""T7 safety validator and formatter tests."""

import logging
from decimal import Decimal

from sqlalchemy import select

from app.config import Settings
from app.data.models import CheckEvent
from app.engine import CheckInput, CheckStatus, InputType, Language, run_check
from app.engine.format import format_fallback, format_result, format_status_message
from app.engine.llm import LLMResponse
from app.engine.types import DraftOutput, RuleHit
from app.engine.validate import validate
from tests.support import addressed_rule_ids


class SequenceLLMProvider:
    def __init__(self, drafts: list[DraftOutput]) -> None:
        self.drafts = drafts
        self.calls: list[dict] = []

    async def analyze(self, **kwargs) -> LLMResponse:
        self.calls.append(kwargs)
        draft = self.drafts[min(len(self.calls) - 1, len(self.drafts) - 1)]
        draft = draft.model_copy(
            update={"addressed_rule_ids": addressed_rule_ids(kwargs["user"])}
        )
        return LLMResponse(draft=draft, input_tokens=100, output_tokens=40)


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        telegram_token="token",
        database_url="postgresql+asyncpg://avvalo:avvalo@localhost:5432/avvalo",
        app_hmac_secret="test-hmac-secret",
        llm_base_url="http://localhost:11434/v1",
        llm_api_key="ollama",
        llm_model="qwen2.5:7b-instruct",
        llm_in_rate_per_m=1.0,
        llm_out_rate_per_m=2.0,
        web_session_secret="test-web-session-secret",
    )


def _clean_draft() -> DraftOutput:
    return DraftOutput(
        red_flags=["The message asks for a one-time code."],
        pattern="Authority pressure and urgency.",
        verify=["Open the bank app yourself before acting."],
        ask=["Ask which official channel shows this request."],
    )


def test_validator_rejects_verdict_words_contacts_and_unsafe_instructions() -> None:
    rule_hits = [RuleHit(rule_id="fs.credential.otp", family="credential_theft", message_key="otp")]

    assert not validate(
        DraftOutput(
            red_flags=["This is safe."],
            verify=["Open the official app yourself."],
            ask=["Who are you?"],
        ),
        [],
        rule_hits,
        Language.uz_latn,
    ).ok
    assert not validate(
        DraftOutput(
            red_flags=["Это безопасно."],
            verify=["Open the official app yourself."],
            ask=["Who are you?"],
        ),
        [],
        rule_hits,
        Language.uz_latn,
    ).ok
    assert not validate(
        DraftOutput(
            red_flags=["Bu xavfsiz."],
            verify=["Open the official app yourself."],
            ask=["Who are you?"],
        ),
        [],
        rule_hits,
        Language.ru,
    ).ok
    assert not validate(
        DraftOutput(
            red_flags=["Call +998 71 200 00 00."],
            verify=["Open the official app yourself."],
            ask=["Who are you?"],
        ),
        [],
        rule_hits,
        Language.ru,
    ).ok
    assert not validate(
        DraftOutput(
            red_flags=["Passport AA1234567 is requested."],
            verify=["Open the official app yourself."],
            ask=["Who are you?"],
        ),
        [],
        rule_hits,
        Language.ru,
    ).ok
    assert not validate(
        DraftOutput(
            red_flags=["It asks for a fee."],
            verify=["Open the link to check the request."],
            ask=["Who are you?"],
        ),
        [],
        rule_hits,
        Language.ru,
    ).ok


def test_validator_rejects_direct_verdicts_scores_lookup_claims_and_bare_domains() -> None:
    unsafe_texts = (
        "Это мошенничество.",
        "Это является мошенничеством.",
        "Bu firibgarlik.",
        "Bu firibgarlikdir.",
        "Бу фирибгарлик.",
        "Risk score: 95%.",
        "There is a 95 percent chance of danger.",
        "Уровень риска: 9/10.",
        "The external database shows no matches.",
        "По базе данных совпадений нет.",
        "Tashqi bazada bu hisob tasdiqlandi.",
        "Use bank.uz to verify.",
    )

    for unsafe_text in unsafe_texts:
        result = validate(
            DraftOutput(
                red_flags=[unsafe_text],
                verify=["Use an independent official channel."],
                ask=["What can be confirmed independently?"],
            ),
            [],
            [],
            Language.ru,
        )
        assert not result.ok, unsafe_text

    allowed_percentage = validate(
        DraftOutput(
            red_flags=["The message promises a 20% investment return."],
            verify=["Check the written terms independently."],
            ask=["What documents support the promised return?"],
        ),
        [],
        [],
        Language.ru,
    )
    assert allowed_percentage.ok


def test_validator_accepts_clean_draft_and_truncates_blocks() -> None:
    draft = DraftOutput(
        red_flags=["one", "two", "three", "four"],
        verify=["one", "two", "three", "four"],
        ask=["one", "two", "three", "four"],
    )

    result = validate(
        draft,
        [],
        [RuleHit(rule_id="fs.test", family="test", message_key="test")],
        Language.ru,
    )

    assert result.ok
    assert result.draft.red_flags == ["one", "two", "three"]
    assert result.draft.verify == ["one", "two", "three"]
    assert result.draft.ask == ["one", "two", "three"]


def test_formatter_adds_structure_limitation_and_no_signal_lead() -> None:
    formatted = format_result(_clean_draft(), Language.uz_latn)
    assert "🚩 **Xavf belgilari**" in formatted
    assert "✅ **Nimani tekshiring**" in formatted
    assert "❓ **Qanday savol bering**" in formatted
    assert "odamni tekshirish" in formatted

    no_signal = format_result(
        DraftOutput(
            red_flags=[],
            verify=["Check through a channel you find yourself."],
            ask=["Ask why it cannot wait."],
        ),
        Language.ru,
        no_signal=True,
    )
    assert no_signal.startswith(
        "\u042f\u0432\u043d\u044b\u0445 "
        "\u0442\u0440\u0435\u0432\u043e\u0436\u043d\u044b\u0445 "
        "\u043f\u0440\u0438\u0437\u043d\u0430\u043a\u043e\u0432"
    )
    no_guarantee = (
        "\u041d\u043e \u044d\u0442\u043e \u043d\u0435 "
        "\u0433\u0430\u0440\u0430\u043d\u0442\u0438\u044f"
    )
    assert no_guarantee in no_signal


def test_status_messages_are_localized() -> None:
    assert "Daily" not in format_status_message(CheckStatus.rate_limited, Language.ru)
    assert "Tekshirish" in format_status_message(CheckStatus.empty_input, Language.uz_latn)


def test_status_message_map_covers_every_non_model_status() -> None:
    from app.engine.format import _STATUS_MESSAGES

    # ok / no_signal render the model draft; safety_fallback has its own formatter.
    # Everything else must have an explicit entry so format_status_message()'s
    # unsupported_media fallback never silently mislabels a new status.
    formatted_elsewhere = {CheckStatus.ok, CheckStatus.no_signal, CheckStatus.safety_fallback}
    assert set(_STATUS_MESSAGES) == set(CheckStatus) - formatted_elsewhere
    for translations in _STATUS_MESSAGES.values():
        assert set(translations) == set(Language)
        assert all(text.strip() for text in translations.values())


async def test_pipeline_retries_once_after_validation_failure(session) -> None:
    provider = SequenceLLMProvider(
        [
            DraftOutput(red_flags=["This is safe."], verify=["Open the official app."], ask=["?"]),
            _clean_draft(),
        ]
    )

    result = await run_check(
        CheckInput(
                        user_key="u-t7-retry",
            language=Language.uz_latn,
            input_type=InputType.text,
            raw_text="Bank xavfsizlik xizmatidanmiz. SMS kodni yuboring.",
        ),
        session=session,
        llm_provider=provider,
        settings=_settings(),
    )
    await session.commit()

    assert result.status == CheckStatus.ok
    assert len(provider.calls) == 2
    assert "SAFETY RETRY" in provider.calls[1]["system"]
    assert result.input_tokens == 200
    assert result.output_tokens == 80
    assert result.cost_usd == 0.00036

    stored_event = (await session.execute(select(CheckEvent))).scalar_one()
    assert stored_event.status == "ok"
    assert stored_event.cost_usd == Decimal("0.000360")


async def test_pipeline_returns_safety_fallback_after_double_validation_failure(
    session, caplog
) -> None:
    caplog.set_level(logging.ERROR, logger="app.obs.events")
    provider = SequenceLLMProvider(
        [
            DraftOutput(red_flags=["This is safe."], verify=["Open the link."], ask=["?"]),
            DraftOutput(
                red_flags=["Call +998 90 123 45 67."],
                verify=["Open the link."],
                ask=["?"],
            ),
        ]
    )

    result = await run_check(
        CheckInput(
                        user_key="u-t7-fallback",
            language=Language.uz_latn,
            input_type=InputType.text,
            raw_text="Bank xavfsizlik xizmatidanmiz. SMS kodni yuboring.",
        ),
        session=session,
        llm_provider=provider,
        settings=_settings(),
    )
    await session.commit()

    assert result.status == CheckStatus.safety_fallback
    assert result.safety_blocked is True
    assert result.text == format_fallback(Language.uz_latn)
    assert result.input_tokens == 200
    assert result.output_tokens == 80
    assert len(provider.calls) == 2

    stored_event = (await session.execute(select(CheckEvent))).scalar_one()
    assert stored_event.status == "safety_fallback"
    assert stored_event.safety_blocked is True

    # The rejection reason is a fixed description, never the leaked value itself.
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "event=app_error" in messages
    assert "'stage': 'validate'" in messages
    assert "raw phone number leaked" in messages
    assert "+998 90 123 45 67" not in messages
