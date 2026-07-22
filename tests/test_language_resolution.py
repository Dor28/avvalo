"""Content-language resolution before prompt/formatting."""

from sqlalchemy import select

from app.data.models import CheckEvent
from app.engine import CheckInput, CheckStatus, InputType, Language, run_check
from app.engine.language import resolve_content_language
from app.engine.llm import LLMResponse
from app.engine.types import DraftOutput
from tests.support import addressed_rule_ids


class CapturingLLM:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def analyze(self, **kwargs) -> LLMResponse:
        self.calls.append(kwargs)
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


def test_resolve_content_language_prefers_dominant_content_script() -> None:
    assert (
        resolve_content_language(
            "Bank xavfsizlik xizmatidanmiz. Hozir SMS kodni yuboring.",
            fallback=Language.ru,
        )
        is Language.uz_latn
    )
    assert (
        resolve_content_language(
            "Мама, это мой новый номер. Срочно переведи деньги.",
            fallback=Language.uz_latn,
        )
        is Language.ru
    )

def test_cyrillic_uzbek_is_read_as_uzbek_but_answered_in_latin() -> None:
    # Cyrillic-Uzbek must not be mistaken for Russian, and Uzbek is only ever
    # answered in Latin script.
    assert (
        resolve_content_language(
            "Ҳозир SMS кодни юборинг, акс ҳолда ҳисоб ёпилади.",
            fallback=Language.ru,
        )
        is Language.uz_latn
    )
    assert (
        resolve_content_language(
            "Тўловни қилдим, чек мана. Тезроқ жўнатинг.",
            fallback=Language.ru,
        )
        is Language.uz_latn
    )


async def test_pipeline_uses_detected_content_language_for_prompt_and_event(session) -> None:
    provider = CapturingLLM()

    result = await run_check(
        CheckInput(
                        user_key="lang-content",
            language=Language.ru,
            input_type=InputType.text,
            raw_text="Bank xavfsizlik xizmatidanmiz. Hozir SMS kodni yuboring.",
        ),
        session=session,
        llm_provider=provider,
    )
    await session.commit()

    assert result.status == CheckStatus.ok
    assert result.language is Language.uz_latn
    assert "TARGET LANGUAGE: uz_latn" in provider.calls[0]["user"]

    stored_event = (await session.execute(select(CheckEvent))).scalar_one()
    assert stored_event.language == "uz_latn"
