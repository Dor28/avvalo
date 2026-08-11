FROM python:3.11-slim@sha256:db3ff2e1800a8581e2c48a27c3995339d47bdf046da21c7627accd3d51053a93

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system avvalo \
    && useradd --system --gid avvalo --create-home avvalo

COPY pyproject.toml README.md requirements.lock ./
COPY app ./app
RUN python -m pip install --require-hashes -r requirements.lock \
    && python -m pip install --no-deps --no-build-isolation .

# Local OCR (OCR_PROVIDER=paddleocr) must never touch the network at runtime:
# the production container is read-only, so a first-use model download would
# fail and surface as ocr_error. paddlex reads PADDLE_PDX_CACHE_HOME into a
# module-level constant at import, so pin an absolute path that the build and
# the runtime both resolve — this must not depend on HOME. The source check is
# four outbound HEAD requests made at import; disable it since weights are baked.
ENV PADDLE_PDX_CACHE_HOME=/opt/paddlex \
    PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True

RUN python -m app.engine.ocr.warmup \
    && chmod -R a+rX /opt/paddlex

COPY alembic.ini ./
COPY alembic ./alembic
COPY knowledge ./knowledge
COPY prompts ./prompts
COPY rules ./rules

USER avvalo

CMD ["python", "-m", "app.main"]
