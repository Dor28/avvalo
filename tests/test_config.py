"""T1 configuration contract tests."""

import pytest
from pydantic import ValidationError

from app.config import Settings

REQUIRED_SETTINGS = {
    "telegram_token": "test-token",
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
    assert settings.daily_check_limit == 5
    assert settings.web_enabled is False
    assert settings.admin_access_key is None
    assert "test-api-key" not in repr(settings)


def test_admin_access_key_is_optional_and_secret() -> None:
    settings = Settings(
        _env_file=None,
        admin_access_key="test-admin-editor-key",
        **REQUIRED_SETTINGS,
    )

    assert settings.admin_access_key is not None
    assert settings.admin_access_key.get_secret_value() == "test-admin-editor-key"
    assert "test-admin-editor-key" not in repr(settings)


def test_output_token_limit_cannot_exceed_safety_budget() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, max_output_tokens=601, **REQUIRED_SETTINGS)
