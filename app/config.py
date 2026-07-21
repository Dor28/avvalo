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
    llm_fallback_base_url: str | None = None
    llm_fallback_api_key: SecretStr | None = None
    llm_fallback_model: str | None = None
    knowledge_router_enabled: bool = False
    knowledge_router_base_url: str | None = None
    knowledge_router_api_key: SecretStr | None = None
    knowledge_router_model: str | None = None
    knowledge_router_timeout_s: float = Field(default=10.0, gt=0)
    url_reputation_enabled: bool = False
    urlhaus_feed_url: str | None = None
    openphish_feed_url: str | None = None
    url_feeds_refresh_hours: int = Field(default=12, ge=1, le=168)
    knowledge_gap_default_days: int = Field(default=7, ge=1, le=365)
    knowledge_unavailable_alert_threshold: float = Field(default=0.2, ge=0, le=1)
    knowledge_unavailable_alert_window_minutes: int = Field(default=30, ge=1, le=1440)

    google_application_credentials: str | None = None
    ocr_provider: str = "gcv"
    ocr_min_confidence: float = Field(default=0.5, ge=0, le=1)
    ocr_timeout_s: float = Field(default=30.0, gt=0)

    notice_version: str = "2026-07-07-v2"
    daily_limit_family: int = Field(default=5, ge=1)
    daily_limit_merchants: int = Field(default=20, ge=1)
    operator_alert_chat_id: int | None = None
    operator_alert_debounce_s: float = Field(default=900.0, gt=0)
    story_max_chars: int = Field(default=2000, ge=1, le=10000)
    story_daily_limit: int = Field(default=3, ge=1, le=20)
    story_rejected_retention_days: int = Field(default=30, ge=1)

    # Unset disables Sentry entirely — log_error() falls back to the local log only.
    sentry_dsn: SecretStr | None = None
    sentry_environment: str = "production"

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
