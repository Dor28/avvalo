"""T4 — engine type contracts and pipeline skeleton tests."""

from sqlalchemy import select

from app.data.models import CheckEvent
from app.engine import CheckInput, CheckStatus, InputType, Language, run_check
from app.engine.llm import LLMResponse
from app.engine.ocr import OCRResult
from app.engine.types import DraftOutput


class FakeLLMProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def analyze(self, **_kwargs) -> LLMResponse:
        self.calls += 1
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


class FakeOCRProvider:
    def __init__(self, *, text: str, confidence: float) -> None:
        self.text = text
        self.confidence = confidence
        self.calls = 0

    async def extract(self, image_bytes: bytes) -> OCRResult:
        self.calls += 1
        assert image_bytes
        return OCRResult(text=self.text, confidence=self.confidence)


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
    assert result.language == Language.uz_latn
    assert result.input_type == InputType.text
    assert "fs.credential.otp" in result.rule_ids
    assert "fs.authority.impersonation" in result.rule_ids
    assert result.text

    stored_event = (await session.execute(select(CheckEvent))).scalar_one()
    assert stored_event.user_key == "u1"
    assert stored_event.face == "family_shield"
    assert stored_event.status == "ok"
    assert stored_event.language == "uz_latn"
    assert stored_event.input_type == "text"
    assert "fs.credential.otp" in stored_event.rule_ids


async def test_run_check_image_uses_ocr_and_records_only_metadata(session) -> None:
    ocr_text = (
        "Bank xavfsizlik xizmatidanmiz. Kartangiz bloklanadi. "
        "Hozir SMS orqali kelgan 6 xonali kodni yuboring."
    )
    check_input = CheckInput(
        face="family_shield",
        user_key="u-img",
        language=Language.ru,
        input_type=InputType.image,
        image_bytes=b"private-image-bytes",
    )
    llm = FakeLLMProvider()

    result = await run_check(
        check_input,
        session=session,
        llm_provider=llm,
        ocr_provider=FakeOCRProvider(text=ocr_text, confidence=0.91),
    )
    await session.commit()

    assert result.status == CheckStatus.ok
    assert result.input_type == InputType.image
    assert result.ocr_confidence == 0.91
    assert result.ocr_ms is not None
    assert llm.calls == 1

    stored_event = (await session.execute(select(CheckEvent))).scalar_one()
    assert stored_event.input_type == "image"
    assert stored_event.ocr_confidence == 0.91
    stored_values = [
        str(getattr(stored_event, column.name))
        for column in CheckEvent.__table__.columns
        if getattr(stored_event, column.name) is not None
    ]
    assert "private-image-bytes" not in "".join(stored_values)
    assert "SMS orqali" not in "".join(stored_values)


async def test_run_check_low_ocr_returns_without_llm(session) -> None:
    llm = FakeLLMProvider()
    result = await run_check(
        CheckInput(
            face="family_shield",
            user_key="u-low-ocr",
            language=Language.uz_latn,
            input_type=InputType.image,
            image_bytes=b"private-image-bytes",
        ),
        session=session,
        llm_provider=llm,
        ocr_provider=FakeOCRProvider(text="blurred", confidence=0.2),
    )

    assert result.status == CheckStatus.low_ocr
    assert result.ocr_confidence == 0.2
    assert llm.calls == 0


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
