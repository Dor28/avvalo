FROM python:3.14-slim@sha256:a7fb1e634c4a578f9e0bd6327f11a3cde11b7a9395f48e24360c0988bcc5c2bc

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
