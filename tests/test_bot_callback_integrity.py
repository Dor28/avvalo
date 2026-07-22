"""Telegram callback bindings prevent stale or cross-user state mutations."""

from types import SimpleNamespace

import pytest

from app.bot.handlers import on_consent_accepted, on_feedback
from app.bot.keyboards import consent_callback_data, feedback_callback_data
from app.bot.states import Onboarding
from app.bot.texts import t
from app.config import Settings
from app.data import repo
from app.data.models import Consent, Feedback
from app.engine.faces import FACES
from app.privacy.user_key import derive_user_key


def _settings(**overrides) -> Settings:
    values = {
        "telegram_token": "token",
        "database_url": "postgresql+asyncpg://avvalo:avvalo@localhost:5432/avvalo",
        "app_hmac_secret": "test-hmac-secret",
        "llm_base_url": "http://localhost:11434/v1",
        "llm_api_key": "ollama",
        "llm_model": "qwen2.5:7b-instruct",
        "web_session_secret": "test-web-session-secret",
        "notice_version": "2026-07-21-v3",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


class _SessionFactory:
    def __init__(self, session) -> None:
        self.session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *_exc) -> None:
        return None


class _State:
    def __init__(self, data=None, *, state=None) -> None:
        self.data = dict(data or {})
        self.state = state

    async def get_data(self) -> dict:
        return dict(self.data)

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def get_state(self):
        return getattr(self.state, "state", self.state)

    async def set_state(self, state) -> None:
        self.state = state


class _Bot:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send_message(self, chat_id, text, reply_markup=None) -> None:
        self.messages.append(
            {"chat_id": chat_id, "text": text, "reply_markup": reply_markup}
        )


class _Callback:
    def __init__(self, data: str, *, user_id: int = 123, bot: _Bot | None = None) -> None:
        self.data = data
        self.from_user = SimpleNamespace(id=user_id)
        self.bot = bot
        self.message = None
        self.answers: list[tuple[str | None, dict]] = []

    async def answer(self, text=None, **kwargs) -> None:
        self.answers.append((text, kwargs))


async def _record_check(session, *, user_key: str):
    check_id = await repo.record_check_event(
        session,
        user_key=user_key,
        face="family",
        input_type="text",
        language="ru",
        status="ok",
    )
    await session.commit()
    return check_id


async def test_feedback_callback_updates_its_check_not_latest_fsm_check(session) -> None:
    settings = _settings()
    user_key = derive_user_key(123, secret=settings.app_hmac_secret.get_secret_value())
    first_check_id = await _record_check(session, user_key=user_key)
    latest_check_id = await _record_check(session, user_key=user_key)
    state = _State({"language": "ru", "last_check_id": str(latest_check_id)})

    await on_feedback(
        _Callback(feedback_callback_data("usefulness", "yes", first_check_id)),
        state,
        settings,
        _SessionFactory(session),
        FACES["family"],
    )

    first_feedback = await session.get(Feedback, first_check_id)
    latest_feedback = await session.get(Feedback, latest_check_id)
    assert first_feedback is not None and first_feedback.usefulness == "yes"
    assert latest_feedback is None
    assert state.data["feedback_check_id"] == str(first_check_id)


async def test_feedback_callback_rejects_a_check_owned_by_another_user(session) -> None:
    settings = _settings()
    other_user_key = derive_user_key(999, secret=settings.app_hmac_secret.get_secret_value())
    check_id = await _record_check(session, user_key=other_user_key)
    callback = _Callback(feedback_callback_data("usefulness", "yes", check_id))

    await on_feedback(
        callback,
        _State({"language": "ru"}),
        settings,
        _SessionFactory(session),
        FACES["family"],
    )

    assert await session.get(Feedback, check_id) is None
    assert callback.answers == [(t("feedback_expired", "ru"), {"show_alert": True})]


@pytest.mark.parametrize("language", ["uz_latn", "ru"])
async def test_stale_consent_callback_reissues_current_notice_without_granting(
    session, language: str
) -> None:
    settings = _settings()
    bot = _Bot()
    callback = _Callback(consent_callback_data(language, "2026-01-01-v1"), bot=bot)
    state = _State({"language": language})

    await on_consent_accepted(
        callback,
        state,
        settings,
        _SessionFactory(session),
        FACES["family"],
    )

    user_key = derive_user_key(123, secret=settings.app_hmac_secret.get_secret_value())
    assert await session.get(Consent, (user_key, "family")) is None
    assert state.state == Onboarding.awaiting_consent
    assert callback.answers == [(t("consent_updated", language), {"show_alert": True})]
    assert bot.messages[-1]["text"] == t("privacy_notice", language)
    button = bot.messages[-1]["reply_markup"].inline_keyboard[0][0]
    assert button.callback_data == consent_callback_data(language, settings.notice_version)


async def test_current_consent_callback_grants_exact_notice_version(session) -> None:
    settings = _settings()
    bot = _Bot()
    state = _State(state=Onboarding.awaiting_consent)

    await on_consent_accepted(
        _Callback(consent_callback_data("ru", settings.notice_version), bot=bot),
        state,
        settings,
        _SessionFactory(session),
        FACES["family"],
    )

    user_key = derive_user_key(123, secret=settings.app_hmac_secret.get_secret_value())
    consent = await session.get(Consent, (user_key, "family"))
    assert consent is not None
    assert consent.notice_version == settings.notice_version
    assert consent.language == "ru"
    assert state.state == Onboarding.ready


async def test_current_consent_callback_requires_active_consent_prompt(session) -> None:
    settings = _settings()
    bot = _Bot()
    callback = _Callback(
        consent_callback_data("ru", settings.notice_version),
        bot=bot,
    )

    await on_consent_accepted(
        callback,
        _State({"language": "ru"}),
        settings,
        _SessionFactory(session),
        FACES["family"],
    )

    user_key = derive_user_key(123, secret=settings.app_hmac_secret.get_secret_value())
    assert await session.get(Consent, (user_key, "family")) is None
    assert callback.answers == [(t("consent_updated", "ru"), {"show_alert": True})]
