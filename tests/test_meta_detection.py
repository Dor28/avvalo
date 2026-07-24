"""Regression coverage for the meta/chitchat short-circuit (app.engine.meta).

Before this existed, every message — including "what can you do" — was forced
through the fraud-check prompt and came back formatted as a situation with
"no red flags found", which read as nonsensical to a user asking a plain
question about the bot.
"""

from app.data import repo
from app.engine import CheckInput, CheckStatus, InputType, Language, run_check
from app.engine.llm import LLMResponse
from app.engine.meta import is_meta_message
from app.engine.types import DraftOutput
from tests.support import addressed_rule_ids


class _CountingLLM:
    def __init__(self) -> None:
        self.calls = 0

    async def analyze(self, **kwargs) -> LLMResponse:
        self.calls += 1
        return LLMResponse(
            draft=DraftOutput(
                red_flags=["The message asks for a one-time code."],
                verify=["Open the official app yourself."],
                ask=["Which official channel shows this request?"],
                addressed_rule_ids=addressed_rule_ids(kwargs["user"]),
            ),
            input_tokens=10,
            output_tokens=5,
        )


def test_is_meta_message_matches_reported_bug_case() -> None:
    assert is_meta_message("что ты можешь")
    assert is_meta_message("Что ты можешь?")
    assert is_meta_message("  ЧТО ТЫ МОЖЕШЬ  ")


def test_is_meta_message_matches_common_greetings_and_capability_questions() -> None:
    for phrase in [
        "привет",
        "Здравствуйте!",
        "кто ты?",
        "help",
        "salom",
        "sen kimsan?",
        "nima qila olasan",
        "rahmat",
        "спасибо",
    ]:
        assert is_meta_message(phrase), phrase


def test_is_meta_message_does_not_match_real_suspicious_content() -> None:
    # These open with a greeting/thanks word but carry an actual situation —
    # must still go through the real check, not be waved off as chitchat.
    for message in [
        "Здравствуйте, ваша карта заблокирована, отправьте код из смс.",
        "Salom, kartangiz bloklandi, hozir kod yuboring.",
        "Спасибо за оплату, но переведите ещё раз на другую карту.",
    ]:
        assert not is_meta_message(message), message


async def test_meta_message_short_circuits_before_llm_and_costs_no_quota(session) -> None:
    llm = _CountingLLM()
    result = await run_check(
        CheckInput(
            user_key="meta-user",
            language=Language.ru,
            input_type=InputType.text,
            raw_text="что ты можешь",
        ),
        session=session,
        llm_provider=llm,
    )

    assert result.status == CheckStatus.meta
    assert result.rule_ids == []
    assert result.text
    assert llm.calls == 0
    assert await repo.get_usage(session, user_key="meta-user", scope="user") == 0


async def test_meta_message_reply_is_localized_per_language(session) -> None:
    result = await run_check(
        CheckInput(
            user_key="meta-uz",
            language=Language.uz_latn,
            input_type=InputType.text,
            raw_text="Salom",
        ),
        session=session,
        llm_provider=_CountingLLM(),
    )
    assert result.status == CheckStatus.meta
    assert result.language == Language.uz_latn
