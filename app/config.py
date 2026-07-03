"""Typed application configuration loaded exclusively from environment variables."""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings shared by every face and channel."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    telegram_token: SecretStr

    database_url: str
    app_hmac_secret: SecretStr

    llm_base_url: str
    llm_api_key: SecretStr
    llm_model: str
    llm_in_rate_per_m: float = Field(default=0.0, ge=0)
    llm_out_rate_per_m: float = Field(default=0.0, ge=0)
    llm_timeout_s: float = Field(default=30.0, gt=0)
    max_output_tokens: int = Field(default=600, ge=1, le=600)

    google_application_credentials: str | None = None
    ocr_provider: str = "gcv"
    ocr_min_confidence: float = Field(default=0.5, ge=0, le=1)
    ocr_timeout_s: float = Field(default=30.0, gt=0)

    notice_version: str = "2026-06-24-v1"
    daily_limit_family: int = Field(default=5, ge=1)
    daily_limit_merchants: int = Field(default=20, ge=1)
    operator_alert_chat_id: int | None = None

    web_enabled: bool = False
    web_host: str = "0.0.0.0"
    web_port: int = Field(default=8000, ge=1, le=65535)
    turnstile_site_key: SecretStr | None = None
    turnstile_secret: SecretStr | None = None
    web_session_secret: SecretStr
    web_daily_limit: int = Field(default=5, ge=1)
    # Set WEB_COOKIE_SECURE=true behind HTTPS in production so the session
    # cookie is never sent over plaintext. Defaults off for local http dev.
    web_cookie_secure: bool = False

    def daily_limit_for(self, face_id: str) -> int | None:
        """Return the configured daily check limit for *face_id*, or None.

        Lets ``DAILY_LIMIT_FAMILY`` / ``DAILY_LIMIT_MERCHANTS`` actually
        drive the per-face limit instead of being inert configuration.
        """

        return {
            "family": self.daily_limit_family,
            "merchants": self.daily_limit_merchants,
        }.get(face_id)


@lru_cache
def get_settings() -> Settings:
    """Return the validated process-wide configuration."""

    return Settings()  # type: ignore[call-arg]
