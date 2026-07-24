"""Local QR intake, routing, ambiguity, and privacy contracts."""

import json
import logging
from pathlib import Path

from sqlalchemy import select

from app.data.models import CheckEvent
from app.engine import CheckInput, CheckStatus, InputType, Language, run_check
from app.engine.llm import LLMResponse
from app.engine.ocr import OCRResult
from app.engine.qr import QRDecoderError, QRDecodeResult, ZXingQRCodeDecoder
from app.engine.types import DraftOutput
from tests.support import addressed_rule_ids

_GOLDEN_DIR = Path(__file__).resolve().parent / "fixtures" / "golden"
_CHECKS_PATH = _GOLDEN_DIR / "checks.json"


class _LowConfidenceOCR:
    calls = 0

    async def extract(self, _image_bytes: bytes) -> OCRResult:
        self.calls += 1
        return OCRResult(text="", confidence=0.0)


class _FakeQRDecoder:
    def __init__(self, *payloads: str) -> None:
        self.payloads = payloads

    async def decode(self, _image_bytes: bytes) -> QRDecodeResult:
        return QRDecodeResult(payloads=self.payloads)


class _FailingQRDecoder:
    async def decode(self, _image_bytes: bytes) -> QRDecodeResult:
        raise QRDecoderError(
            "decoder saw private payload https://do-not-log.example",
            error_code="DecoderFailure",
        )


class _CapturingLLM:
    def __init__(self) -> None:
        self.calls = 0
        self.user_prompt = ""

    async def analyze(self, **kwargs) -> LLMResponse:
        self.calls += 1
        self.user_prompt = kwargs["user"]
        return LLMResponse(
            draft=DraftOutput(
                red_flags=["A local shape signal needs an independent check."],
                verify=["Open the official service yourself."],
                ask=["Why must this destination be used?"],
                addressed_rule_ids=addressed_rule_ids(kwargs["user"]),
            ),
            input_tokens=30,
            output_tokens=20,
        )


def _image_input(*, user_key: str = "qr-user") -> CheckInput:
    return CheckInput(
        user_key=user_key,
        language=Language.uz_latn,
        input_type=InputType.image,
        image_bytes=b"ephemeral-image",
    )


async def test_zxing_decoder_reads_local_qr_fixture() -> None:
    image_bytes = (_GOLDEN_DIR / "qr" / "shortened_url.png").read_bytes()

    result = await ZXingQRCodeDecoder().decode(image_bytes)

    assert result.payloads == ("https://bit.ly/pay-now",)


async def test_qr_goldens_flow_through_the_shared_pipeline() -> None:
    fixtures = json.loads(_CHECKS_PATH.read_text(encoding="utf-8"))
    image_fixtures = [case for case in fixtures if case["input_type"] == "image"]
    assert len(image_fixtures) >= 5

    for case in image_fixtures:
        llm = _CapturingLLM()
        image_bytes = (_GOLDEN_DIR / case["input"]).read_bytes()
        result = await run_check(
            CheckInput(
                user_key=f"golden-{case['id']}",
                language=Language(case["language"]),
                input_type=InputType.image,
                image_bytes=image_bytes,
            ),
            llm_provider=llm,
            ocr_provider=_LowConfidenceOCR(),
        )

        assert result.status.value == case["expected_status"], case["id"]
        for signal_kind in case["expected_signal_kinds"]:
            assert f'"kind": "{signal_kind}"' in llm.user_prompt, case["id"]
        for family in case["expected_rule_families"]:
            assert f"family={family}" in llm.user_prompt, case["id"]


async def test_multiple_qr_codes_are_not_arbitrarily_selected() -> None:
    ocr = _LowConfidenceOCR()
    llm = _CapturingLLM()

    result = await run_check(
        _image_input(user_key="multiple-qr"),
        llm_provider=llm,
        ocr_provider=ocr,
        qr_decoder=_FakeQRDecoder("https://one.example", "https://two.example"),
    )

    assert result.status == CheckStatus.low_ocr
    assert result.error_class == "MultipleQRCodes"
    assert llm.calls == 0
    assert ocr.calls == 0


async def test_emvco_payload_becomes_typed_signal_without_parsed_claims() -> None:
    payload = "0002010102115204000053038605802UZ5911PRIVATE SHOP6304ABCD"
    llm = _CapturingLLM()

    result = await run_check(
        _image_input(user_key="payment-qr"),
        llm_provider=llm,
        ocr_provider=_LowConfidenceOCR(),
        qr_decoder=_FakeQRDecoder(payload),
    )

    assert result.status == CheckStatus.ok
    assert '"kind": "payment_qr"' in llm.user_prompt
    assert "[PAYMENT_QR]" in llm.user_prompt
    assert payload not in llm.user_prompt
    assert "PRIVATE SHOP" not in llm.user_prompt


async def test_decoded_payload_is_minimized_and_never_persisted_or_logged(
    session, caplog
) -> None:
    caplog.set_level(logging.INFO, logger="app.obs.events")
    payload = "https://private-checkout.example/pay?invoice=SECRET-QR-481516"
    llm = _CapturingLLM()

    result = await run_check(
        _image_input(user_key="private-qr"),
        session=session,
        llm_provider=llm,
        ocr_provider=_LowConfidenceOCR(),
        qr_decoder=_FakeQRDecoder(payload),
    )
    await session.commit()

    assert result.status == CheckStatus.ok
    assert "[LINK]" in llm.user_prompt
    assert payload not in llm.user_prompt
    event = (await session.execute(select(CheckEvent))).scalar_one()
    stored_values = "".join(
        str(getattr(event, column.name))
        for column in CheckEvent.__table__.columns
        if getattr(event, column.name) is not None
    )
    assert payload not in stored_values
    assert "SECRET-QR-481516" not in "\n".join(record.getMessage() for record in caplog.records)


async def test_qr_decoder_failure_logs_only_a_fixed_error_class(caplog) -> None:
    caplog.set_level(logging.ERROR, logger="app.obs.events")
    llm = _CapturingLLM()

    result = await run_check(
        _image_input(user_key="qr-decoder-failure"),
        llm_provider=llm,
        ocr_provider=_LowConfidenceOCR(),
        qr_decoder=_FailingQRDecoder(),
    )

    assert result.status == CheckStatus.low_ocr
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "'stage': 'qr'" in messages
    assert "'error_type': 'DecoderFailure'" in messages
    assert "do-not-log.example" not in messages
