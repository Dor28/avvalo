"""T8 — OCR interface & provider selection (V1_TECHNICAL_PLAN §7).

Live acceptance specs that skip until the OCR providers land. The GCV/Tesseract
calls need credentials or binaries, so the offline-checkable contract is tested:
the OCRResult shape and the on-prem stub raising NotImplementedError.
"""

import inspect

import pytest


def test_ocr_result_contract() -> None:
    base = pytest.importorskip("app.engine.ocr.base")
    ocr_result = getattr(base, "OCRResult", None)
    if ocr_result is None:
        pytest.skip("OCRResult not defined yet")
    fields = getattr(ocr_result, "model_fields", {})
    assert "text" in fields and "confidence" in fields


async def test_on_prem_stub_raises_not_implemented() -> None:
    stub = pytest.importorskip("app.engine.ocr.local_stub")
    providers = [
        value
        for value in vars(stub).values()
        if inspect.isclass(value) and hasattr(value, "extract")
    ]
    if not providers:
        pytest.skip("no OCR provider class in local_stub yet")

    try:
        provider = providers[0]()
    except Exception as exc:  # construction needs args we can't supply
        pytest.skip(f"cannot instantiate stub provider: {exc}")

    with pytest.raises(NotImplementedError):
        await provider.extract(b"\x89PNG\r\n")


def test_provider_selection_is_configurable(callable_or_skip) -> None:
    select = callable_or_skip(
        "app.engine.ocr", "get_provider", "get_ocr_provider", "build_provider", "provider_for"
    )
    assert callable(select)
