FROM python:3.14-slim@sha256:656d12e70054d5fda18a045e2494c96701e9792dd1445f95b3d038df954f57e9

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system avvalo \
    && useradd --system --gid avvalo --create-home avvalo

COPY pyproject.toml README.md requirements.lock ./
COPY app ./app
# --no-deps: requirements.lock is the complete resolved closure, so pip installs
# exactly it rather than re-resolving from each wheel's metadata. That is what
# lets opencv-python-headless stand in for the X11-linked opencv-python that
# rapidocr names in its own requirements.
RUN python -m pip install --require-hashes --no-deps -r requirements.lock \
    && python -m pip install --no-deps --no-build-isolation .

# Download the OCR models into the image through the provider's own warmup, so
# the weights baked in here are exactly the ones it loads at run time. The
# container then needs neither a writable directory nor network access for OCR,
# which is what lets it run with read_only: true. A failure here fails the
# build on purpose — models cannot be fetched later on a read-only filesystem.
RUN python -c "import asyncio; from app.engine.ocr.rapidocr import RapidOCRProvider; asyncio.run(RapidOCRProvider().warmup())"

COPY alembic.ini ./
COPY alembic ./alembic
COPY knowledge ./knowledge
COPY prompts ./prompts
COPY rules ./rules

USER avvalo

CMD ["python", "-m", "app.main"]
