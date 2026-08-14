"""RapidOCR provider — PP-OCRv5 recognition models on ONNX Runtime.

The same detection and recognition models PaddleOCR ships, exported to ONNX and
run under ``onnxruntime`` instead of ``paddlepaddle``. That keeps PP-OCRv5's
accuracy while dropping the paddle/paddlex dependency tree, and it lets the
model weights be baked into the container image, so the provider needs no
writable directory and no network access at run time.
"""

from __future__ import annotations

import asyncio
import threading
from contextlib import suppress
from io import BytesIO
from typing import Any

from PIL import Image

from app.engine.ocr.base import (
    OCRInvalidImageError,
    OCRProviderError,
    OCRResult,
    script_match_score,
    strip_image_metadata,
)

# PP-OCRv5 splits recognition by script rather than by language, so a submitted
# screenshot is tried against both scripts Avvalo accepts and the better result
# wins. "latin" is the model whose 32-language training set includes Uzbek;
# "cyrillic" is preferred over the narrower "eslav" (Russian/Belarusian/
# Ukrainian/English only) because Cyrillic-Uzbek input is still supported at
# intake and needs ў/қ/ғ/ҳ in the character set.
_DEFAULT_SCRIPTS: tuple[str, ...] = ("latin", "cyrillic")


class RapidOCRProvider:
    """Run PP-OCRv5 models locally through ONNX Runtime.

    Runs every configured script and keeps the best result by
    :func:`_script_score`. Both always run: which script a screenshot is in is
    not known before OCR, and the pipeline resolves language from the OCR text
    afterwards, so there is nothing earlier to select on.

    Engines are built once and reused; :meth:`warmup` loads them at boot so no
    user pays the first-load cost. ``model_root_dir`` overrides where weights
    are read from — the default is the ``rapidocr`` package directory, which
    the image populates at build time.
    """

    def __init__(
        self,
        *,
        scripts: tuple[str, ...] = _DEFAULT_SCRIPTS,
        model_root_dir: str | None = None,
    ) -> None:
        self.scripts = scripts
        self.model_root_dir = model_root_dir
        self._engines: dict[str, Any] = {}
        # Engines are built inside worker threads and shared across concurrent
        # checks; the lock keeps two callers from loading the same model twice.
        self._engine_lock = threading.Lock()

    async def extract(self, image_bytes: bytes) -> OCRResult:
        """Extract text with local RapidOCR in a worker thread."""

        stripped = strip_image_metadata(image_bytes)
        return await asyncio.to_thread(self._extract_sync, stripped)

    async def warmup(self) -> None:
        """Load every configured script model before the first check."""

        await asyncio.to_thread(self._load_engines)

    def _load_engines(self) -> None:
        import numpy as np

        # Building the engine resolves its model files, and one pass over a
        # blank frame then forces anything the pipeline fetches lazily —
        # detector, angle classifier, recognizer. The image build runs this so
        # a read-only container never has to download a model at run time.
        # Only that probe pass is tolerant: a frame with no text in it may
        # legitimately fail, while a missing model still fails engine
        # construction above and stops the build.
        probe = np.zeros((32, 32, 3), dtype="uint8")
        for script in self.scripts:
            engine = self._engine(script)
            with suppress(Exception):
                engine(probe)

    def _extract_sync(self, image_bytes: bytes) -> OCRResult:
        try:
            import numpy as np

            with Image.open(BytesIO(image_bytes)) as image:
                array = np.array(image.convert("RGB"))
        except Exception as exc:
            raise OCRInvalidImageError(
                "rapidocr could not decode the image", error_code=type(exc).__name__
            ) from exc

        best: OCRResult | None = None
        best_score = -1.0
        for script in self.scripts:
            try:
                candidate = self._run_engine(script, array)
            except Exception as exc:
                raise OCRProviderError(
                    "rapidocr OCR failed; ensure rapidocr and onnxruntime are installed",
                    error_code=type(exc).__name__,
                ) from exc

            score = script_match_score(candidate)
            if score > best_score:
                best, best_score = candidate, score

        return best or OCRResult(text="", confidence=0.0)

    def _engine(self, script: str) -> Any:
        engine = self._engines.get(script)
        if engine is not None:
            return engine

        with self._engine_lock:
            engine = self._engines.get(script)
            if engine is None:
                engine = self._build_engine(script)
                self._engines[script] = engine
            return engine

    def _build_engine(self, script: str) -> Any:
        from rapidocr import EngineType, LangDet, LangRec, ModelType, OCRVersion, RapidOCR

        params: dict[str, Any] = {
            "Det.engine_type": EngineType.ONNXRUNTIME,
            # One detector serves every script: detection finds text boxes and
            # is script-agnostic, only recognition needs the per-script model.
            # PP-OCRv5 publishes exactly one — ch_PP-OCRv5_det_{mobile,server} —
            # so `ch` here is the general detector, not a language choice, and
            # any other value fails model lookup with "Invalid OCR configuration".
            "Det.lang_type": LangDet.CH,
            "Det.model_type": ModelType.MOBILE,
            "Det.ocr_version": OCRVersion.PPOCRV5,
            "Rec.engine_type": EngineType.ONNXRUNTIME,
            "Rec.lang_type": LangRec(script),
            "Rec.model_type": ModelType.MOBILE,
            "Rec.ocr_version": OCRVersion.PPOCRV5,
        }
        if self.model_root_dir is not None:
            params["Global.model_root_dir"] = self.model_root_dir
        return RapidOCR(params=params)

    def _run_engine(self, script: str, image: Any) -> OCRResult:
        result = self._engine(script)(image)

        texts = tuple(getattr(result, "txts", None) or ())
        scores = [float(score) for score in (getattr(result, "scores", None) or ())]
        text = "\n".join(str(value) for value in texts if value).strip()
        confidence = (sum(scores) / len(scores)) if scores else 0.0
        return OCRResult(text=text, confidence=max(0.0, min(1.0, confidence)))


__all__ = ["RapidOCRProvider"]
