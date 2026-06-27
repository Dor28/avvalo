"""T1 configuration contract tests."""

import pytest
from pydantic import ValidationError

from app.config import Settings

REQUIRED_SETTINGS = {
    "telegram_token_family_shield": "test-token",
    "database_url": "postgresql+asyncpg://avvalo:avvalo@localhost:5432/avvalo",
    "app_hmac_secret": "test-hmac-secret",
    "llm_base_url": "https://example.invalid/v1",
    "llm_api_key": "test-api-key",
    "llm_model": "qwen-test",
    "web_session_secret": "test-web-session-secret",
}


def test_settings_load_required_values() -> None:
    settings = Settings(_env_file=None, **REQUIRED_SETTINGS)

    assert settings.max_output_tokens == 600
    assert settings.ocr_provider == "gcv"
    assert settings.daily_limit_family_shield == 5
    assert settings.daily_limit_seller_guard == 20
    assert settings.web_enabled is False
    assert "test-api-key" not in repr(settings)


def test_output_token_limit_cannot_exceed_safety_budget() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, max_output_tokens=601, **REQUIRED_SETTINGS)
