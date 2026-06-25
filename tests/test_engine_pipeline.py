"""T4 — engine type contracts and pipeline skeleton tests."""

from sqlalchemy import select

from app.data.models import CheckEvent
from app.engine import CheckInput, CheckStatus, InputType, Language, run_check
from app.engine.llm import LLMResponse
from app.engine.types import DraftOutput


class FakeLLMProvider:
    async def analyze(self, **_kwargs) -> LLMResponse:
        return LLMResponse(
            draft=DraftOutput(
                red_flags=["Detected local warning sign."],
                pattern="authority pressure",
                verify=["Use an official channel you find yourself."],
                ask=["Ask why this cannot wait."],
            ),
            input_tokens=100,
            output_tokens=50,
        )


async def test_run_check_text_returns_result_and_records_event(session) -> None:
    check_input = CheckInput(
        face="family_shield",
        user_key="u1",
        language=Language.ru,
        input_type=InputType.text,
        raw_text=(
            "Bank xavfsizlik xizmatidanmiz. Kartangiz bloklanadi. "
            "Hozir SMS orqali kelgan 6 xonali kodni yuboring."
        ),
    )

    result = await run_check(check_input, session=session, llm_provider=FakeLLMProvider())
    await session.commit()

    assert result.status == CheckStatus.ok
    assert result.language == Language.ru
    assert result.input_type == InputType.text
    assert "fs.credential.otp" in result.rule_ids
    assert "fs.authority.impersonation" in result.rule_ids
    assert result.text

    stored_event = (await session.execute(select(CheckEvent))).scalar_one()
    assert stored_event.user_key == "u1"
    assert stored_event.face == "family_shield"
    assert stored_event.status == "ok"
    assert stored_event.language == "ru"
    assert stored_event.input_type == "text"
    assert "fs.credential.otp" in stored_event.rule_ids


async def test_run_check_never_persists_ephemeral_input(session) -> None:
    raw_text = "Transfer to raw-card 8600123412345678 and call +998901234567."
    check_input = CheckInput(
        face="family_shield",
        user_key="u2",
        language=Language.uz_latn,
        input_type=InputType.text,
        raw_text=raw_text,
        caption="private caption",
    )

    await run_check(check_input, session=session, llm_provider=FakeLLMProvider())
    await session.commit()

    stored_event = (await session.execute(select(CheckEvent))).scalar_one()
    stored_values = [
        str(getattr(stored_event, column.name))
        for column in CheckEvent.__table__.columns
        if getattr(stored_event, column.name) is not None
    ]

    assert raw_text not in stored_values
    assert "private caption" not in stored_values
    assert "8600123412345678" not in "".join(stored_values)
    assert "+998901234567" not in "".join(stored_values)


async def test_run_check_empty_text_returns_empty_input(session) -> None:
    result = await run_check(
        CheckInput(
            face="family_shield",
            user_key="u3",
            language=Language.uz_cyrl,
            input_type=InputType.text,
            raw_text="   ",
        ),
        session=session,
    )

    assert result.status == CheckStatus.empty_input
    assert result.rule_ids == []
