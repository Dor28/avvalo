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

COPY alembic.ini ./
COPY alembic ./alembic
COPY knowledge ./knowledge
COPY prompts ./prompts
COPY rules ./rules

USER avvalo

CMD ["python", "-m", "app.main"]
