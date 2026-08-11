"""Build-time PaddleOCR model warmup so production never downloads at runtime.

Run once while building the image (``python -m app.engine.ocr.warmup``); see the
warmup layer in the Dockerfile. Three production facts make this mandatory
rather than an optimization:

* PaddleOCR resolves an uncached model by downloading it on first use, so
  without this the *first real user check* pays the download.
* The production container runs ``read_only: true`` with no writable model
  cache, so that download would fail outright and surface as ``ocr_error``.
* paddlex reads ``PADDLE_PDX_CACHE_HOME`` into a module-level constant at import
  time, so the build and the runtime must resolve the same absolute path — the
  Dockerfile pins it instead of relying on ``~/.paddlex`` and a stable ``HOME``.

Weights are fetched through the real provider, one language at a time, so the
constructor arguments here can never drift from the ones production uses.
"""

from __future__ import annotations

import asyncio
import sys

from app.engine.ocr.base import probe_image
from app.engine.ocr.paddleocr import DEFAULT_LANGS, PaddleOCRProvider


def main(langs: tuple[str, ...] = DEFAULT_LANGS) -> int:
    """Fetch and exercise the detection, recognition, and orientation models."""

    image = probe_image()
    for lang in langs:
        # A blank image yields no text; the point is that the weights download,
        # load, and run. Any failure raises and fails the build loudly, which is
        # the whole reason this runs at build time instead of in production.
        result = asyncio.run(PaddleOCRProvider(langs=(lang,)).extract(image))
        print(f"paddleocr warmup ok: lang={lang} confidence={result.confidence:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
