"""Infrastructure and dependency-boundary contract tests.

``config.py`` is covered separately; this module pins the surrounding deployment
services, documented environment surface, and deliberately small dependency stack.
"""

import re
import tomllib
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

# §1.1 environment surface that .env.example must document.
REQUIRED_ENV_VARS = (
    "TELEGRAM_TOKEN",
    "DATABASE_URL",
    "APP_HMAC_SECRET",
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_MODEL",
    "OCR_MIN_CONFIDENCE",
    "NOTICE_VERSION",
    "DAILY_CHECK_LIMIT",
    "LLM_TIMEOUT_S",
    "OCR_TIMEOUT_S",
    "MAX_OUTPUT_TOKENS",
    "WEB_ENABLED",
    "WEB_SESSION_SECRET",
    "TURNSTILE_SITE_KEY",
    "TURNSTILE_SECRET",
    "WEB_DAILY_LIMIT",
)

# §1 locked stack — these must be declared; the "do not add" list must not.
LOCKED_DEPS = {
    "aiogram",
    "fastapi",
    "sqlalchemy",
    "alembic",
    "apscheduler",
    "openai",
    "google-cloud-vision",
    "pydantic-settings",
    "pyyaml",
    "langdetect",
    "jinja2",
    "pillow",
    "uvicorn",
    "asyncpg",
}
FORBIDDEN_DEPS = {"redis", "celery", "kafka", "aiokafka", "aio-pika", "kombu", "flask", "django"}


def _compose() -> dict:
    return yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8"))


def test_compose_defines_db_and_app() -> None:
    services = _compose()["services"]
    assert "db" in services and "app" in services
    assert "postgres" in services["db"]["image"], "db must be a Postgres image (§1)"


def test_ollama_is_behind_the_local_llm_profile() -> None:
    services = _compose()["services"]
    assert "ollama" in services, "optional local LLM service missing (§1.2)"
    profiles = services["ollama"].get("profiles", [])
    assert "local-llm" in profiles, "ollama must be opt-in via the local-llm profile"


def test_app_depends_on_db() -> None:
    depends = _compose()["services"]["app"]["depends_on"]
    names = depends if isinstance(depends, list) else list(depends)
    assert "db" in names


def test_env_example_documents_required_vars() -> None:
    text = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    missing = [var for var in REQUIRED_ENV_VARS if f"{var}=" not in text]
    assert not missing, f".env.example missing §1.1 vars: {missing}"


def test_pyproject_pins_locked_stack_and_excludes_forbidden() -> None:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared = {
        re.split(r"[<>=!~\[ ]", dep, maxsplit=1)[0].lower()
        for dep in data["project"]["dependencies"]
    }
    assert LOCKED_DEPS.issubset(declared), f"missing locked deps: {LOCKED_DEPS - declared}"
    present = FORBIDDEN_DEPS & declared
    assert not present, f"forbidden deps present (§1 'do not add'): {present}"
