FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY app ./app
RUN python -m pip install --upgrade pip && python -m pip install .

COPY alembic.ini ./
COPY alembic ./alembic
COPY prompts ./prompts
COPY rules ./rules

CMD ["python", "-m", "app.main"]

