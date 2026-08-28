"""Telegram onboarding, consent-gate, deletion, and intake handler behavior (§12).

``test_bot_callback_integrity`` covers the callback bindings that guard against
stale or cross-user state. This module covers the surrounding message lifecycle:
the consent gate that decides whether content is accepted at all, the privacy and
deletion commands, and the intake path that turns a Telegram message into a
``CheckInput`` (or refuses to).

The consent gate is the privacy-critical one: content must never reach the engine
before the *current* notice version has been accepted, and the decision is re-read
from the database rather than trusted from FSM state.
"""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.bot.handlers import (
    _build_check_input,
    _download_photo,
    cmd_delete_my_data,
    cmd_privacy,
    cmd_start,
    on_content,
    on_language_chosen,
)
from app.bot.states import Onboarding
from app.bot.texts import DEFAULT_LANGUAGE, entry_text, t
from app.config import Settings
from app.data import repo
from app.data.models import CheckEvent, Consent
from app.engine.types import (
    MAX_IMAGE_BYTES,
    MAX_SUBMITTED_TEXT_CHARS,
    CheckResult,
    CheckStatus,
    InputType,
    Language,
)
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
        self.cleared = False

    async def get_data(self) -> dict:
        return dict(self.data)

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def get_state(self):
        return getattr(self.state, "state", self.state)

    async def set_state(self, state) -> None:
        self.state = state

    async def clear(self) -> None:
        self.cleared = True
        self.data.clear()
        self.state = None


class _Message:
    """A Telegram message that records what was answered."""

    def __init__(
        self,
        *,
        text: str | None = None,
        caption: str | None = None,
        photo=None,
        user_id: int | None = 123,
        bot=None,
    ) -> None:
        self.text = text
        self.caption = caption
        self.photo = photo or []
        self.from_user = None if user_id is None else SimpleNamespace(id=user_id)
        self.bot = bot
        self.replies: list[dict] = []

    async def answer(self, text, reply_markup=None) -> None:
        self.replies.append({"text": text, "reply_markup": reply_markup})

    @property
    def last_reply(self) -> str:
        return self.replies[-1]["text"]


class _Callback:
    def __init__(self, data: str, *, user_id: int = 123) -> None:
        self.data = data
        self.from_user = SimpleNamespace(id=user_id)
        self.bot = None
        self.message = None
        self.answers: list[tuple[str | None, dict]] = []

    async def answer(self, text=None, **kwargs) -> None:
        self.answers.append((text, kwargs))


def _user_key(settings: Settings, user_id: int = 123) -> str:
    return derive_user_key(user_id, secret=settings.app_hmac_secret.get_secret_value())


async def _grant_consent(session, settings: Settings, *, language: str, version=None) -> None:
    await repo.upsert_consent(
        session,
        user_key=_user_key(settings),
        language=language,
        notice_version=version or settings.notice_version,
    )
    await session.commit()


# ── onboarding ──────────────────────────────────────────────────────────────


async def test_start_offers_language_choice_when_consent_is_absent(session) -> None:
    settings = _settings()
    message = _Message(text="/start")
    state = _State()

    await cmd_start(message, state, settings, _SessionFactory(session))

    assert state.state == Onboarding.choosing_language
    assert message.replies[-1]["reply_markup"] is not None, "language keyboard must be offered"


async def test_start_skips_onboarding_for_a_user_with_current_consent(session) -> None:
    settings = _settings()
    await _grant_consent(session, settings, language="ru")
    message = _Message(text="/start")
    state = _State()

    await cmd_start(message, state, settings, _SessionFactory(session))

    assert state.state == Onboarding.ready
    assert state.data["language"] == "ru"
    assert message.last_reply == entry_text("ru")
    assert message.replies[-1]["reply_markup"] is None


async def test_start_re_onboards_when_the_notice_version_moved_on(session) -> None:
    """Bumping ``NOTICE_VERSION`` must force re-consent, not silently pass."""

    settings = _settings()
    await _grant_consent(session, settings, language="ru", version="2020-01-01-v0")
    message = _Message(text="/start")
    state = _State()

    await cmd_start(message, state, settings, _SessionFactory(session))

    assert state.state == Onboarding.choosing_language


async def test_start_ignores_a_message_without_a_sender(session) -> None:
    message = _Message(text="/start", user_id=None)
    state = _State()

    await cmd_start(message, state, _settings(), _SessionFactory(session))

    assert message.replies == []


@pytest.mark.parametrize("language", ["uz_latn", "ru"])
async def test_language_choice_moves_to_the_consent_prompt(language: str) -> None:
    callback = _Callback(f"lang:{language}")
    state = _State()

    await on_language_chosen(callback, state, _settings())

    assert state.data["language"] == language
    assert state.state == Onboarding.awaiting_consent
    assert callback.answers, "the callback must always be acknowledged"


async def test_unknown_language_is_acknowledged_without_changing_state() -> None:
    callback = _Callback("lang:klingon")
    state = _State()

    await on_language_chosen(callback, state, _settings())

    assert "language" not in state.data
    assert state.state is None
    assert callback.answers == [(None, {})]


# ── privacy and deletion ────────────────────────────────────────────────────


@pytest.mark.parametrize("language", ["uz_latn", "ru"])
async def test_privacy_command_answers_in_the_session_language(language: str) -> None:
    message = _Message(text="/privacy")

    await cmd_privacy(message, _State({"language": language}))

    assert message.last_reply == t("privacy", language)


async def test_privacy_command_falls_back_to_the_default_language() -> None:
    message = _Message(text="/privacy")

    await cmd_privacy(message, _State())

    assert message.last_reply == t("privacy", DEFAULT_LANGUAGE)


async def test_delete_my_data_removes_rows_and_clears_the_session(session) -> None:
    settings = _settings()
    await _grant_consent(session, settings, language="ru")
    await repo.record_check_event(
        session,
        user_key=_user_key(settings),
        input_type="text",
        language="ru",
        status="ok",
    )
    await session.commit()
    message = _Message(text="/delete_my_data")
    state = _State({"language": "ru"})

    await cmd_delete_my_data(message, state, settings, _SessionFactory(session))

    assert await session.get(Consent, _user_key(settings)) is None
    assert state.cleared
    assert message.last_reply == t("data_deleted", "ru")


async def test_delete_my_data_ignores_a_message_without_a_sender(session) -> None:
    message = _Message(text="/delete_my_data", user_id=None)

    await cmd_delete_my_data(message, _State(), _settings(), _SessionFactory(session))

    assert message.replies == []


# ── the consent gate on submitted content ───────────────────────────────────


async def test_content_is_refused_before_consent_and_never_reaches_the_engine(session) -> None:
    settings = _settings()
    message = _Message(text="Kartangiz bloklanadi, kodni yuboring")

    await on_content(message, _State(), settings, _SessionFactory(session))

    assert message.last_reply == t("need_consent", DEFAULT_LANGUAGE)
    events = (await session.execute(repo.select(CheckEvent))).scalars().all()
    assert events == [], "no check may be recorded before consent"


async def test_stale_consent_refuses_content_in_the_recorded_language(session) -> None:
    """FSM state is lost on restart, so the refusal language comes from the row."""

    settings = _settings()
    await _grant_consent(session, settings, language="ru", version="2020-01-01-v0")
    message = _Message(text="Ваш счёт заблокирован")

    await on_content(message, _State(), settings, _SessionFactory(session))

    assert message.last_reply == t("need_consent", "ru")


async def test_content_without_a_sender_is_ignored(session) -> None:
    message = _Message(text="hello", user_id=None)

    await on_content(message, _State(), _settings(), _SessionFactory(session))

    assert message.replies == []


async def test_unsupported_input_is_refused_after_consent(session) -> None:
    settings = _settings()
    await _grant_consent(session, settings, language="ru")
    message = _Message(text="   ")

    await on_content(message, _State(), settings, _SessionFactory(session))

    assert message.last_reply == t("unsupported_input", "ru")


# ── intake: message → CheckInput ────────────────────────────────────────────


async def test_text_message_becomes_a_text_check_input() -> None:
    built = await _build_check_input(_Message(text="Kodni yuboring"), user_key="u", language="ru")

    assert built is not None
    assert built.input_type is InputType.text
    assert built.raw_text == "Kodni yuboring"


async def test_caption_is_used_when_a_message_carries_no_text() -> None:
    built = await _build_check_input(
        _Message(caption="Пришлите код"), user_key="u", language="ru"
    )

    assert built is not None
    assert built.raw_text == "Пришлите код"


@pytest.mark.parametrize("payload", ["", "   ", None])
async def test_empty_content_is_unsupported(payload) -> None:
    assert await _build_check_input(_Message(text=payload), user_key="u", language="ru") is None


async def test_text_over_the_cap_is_refused_rather_than_truncated() -> None:
    """Truncating would silently check something the user did not send."""

    oversized = "a" * (MAX_SUBMITTED_TEXT_CHARS + 1)

    assert await _build_check_input(_Message(text=oversized), user_key="u", language="ru") is None


async def test_text_at_the_cap_is_still_accepted() -> None:
    at_cap = "a" * MAX_SUBMITTED_TEXT_CHARS

    built = await _build_check_input(_Message(text=at_cap), user_key="u", language="ru")

    assert built is not None and built.raw_text == at_cap


# ── intake: photo download bounds ───────────────────────────────────────────


class _Bot:
    """A bot whose download writes a fixed payload into the caller's buffer."""

    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    async def download(self, _photo, destination) -> None:
        destination.write(self.payload)


async def test_photo_becomes_an_image_check_input() -> None:
    photo = SimpleNamespace(file_size=10)
    message = _Message(photo=[photo], bot=_Bot(b"image-bytes"), caption="nima bu?")

    built = await _build_check_input(message, user_key="u", language="ru")

    assert built is not None
    assert built.input_type is InputType.image
    assert built.image_bytes == b"image-bytes"
    assert built.caption == "nima bu?"


async def test_photo_declaring_an_oversized_file_is_never_downloaded() -> None:
    """The declared size is checked first, so the transfer never starts."""

    class _RefusingBot:
        async def download(self, _photo, destination):
            raise AssertionError("an oversized photo must not be downloaded")

    photo = SimpleNamespace(file_size=MAX_IMAGE_BYTES + 1)
    message = _Message(photo=[photo], bot=_RefusingBot())

    assert await _download_photo(message) is None


async def test_photo_exceeding_the_cap_mid_download_is_abandoned() -> None:
    """A dishonest or absent ``file_size`` is caught by the bounded buffer."""

    photo = SimpleNamespace(file_size=None)
    message = _Message(photo=[photo], bot=_Bot(b"x" * (MAX_IMAGE_BYTES + 1)))

    assert await _download_photo(message) is None


async def test_empty_download_is_treated_as_unsupported() -> None:
    message = _Message(photo=[SimpleNamespace(file_size=1)], bot=_Bot(b""))

    assert await _download_photo(message) is None


async def test_photo_without_a_bot_cannot_be_downloaded() -> None:
    message = _Message(photo=[SimpleNamespace(file_size=1)], bot=None)

    assert await _download_photo(message) is None


# ── post-check bookkeeping ──────────────────────────────────────────────────


def _stub_run_check(monkeypatch, *, status: CheckStatus, check_id=None, text="reply"):
    """Replace the engine so these tests exercise the handler, not the pipeline."""

    async def _fake(check_input, **kwargs):
        return CheckResult(
            status=status,
            check_id=check_id,
            text=text,
            language=Language(check_input.language),
            input_type=check_input.input_type,
        )

    monkeypatch.setattr("app.bot.handlers.run_check", _fake)


async def test_a_fresh_check_clears_usefulness_left_over_from_the_previous_one(
    session, monkeypatch
) -> None:
    """Otherwise a stale rating could attach to the check the user just sent."""

    settings = _settings()
    await _grant_consent(session, settings, language="ru")
    new_check_id = uuid4()
    _stub_run_check(monkeypatch, status=CheckStatus.ok, check_id=new_check_id)
    state = _State(
        {"feedback_usefulness": "yes", "feedback_check_id": str(uuid4()), "language": "ru"}
    )

    await on_content(_Message(text="Пришлите код"), state, settings, _SessionFactory(session))

    assert state.data["last_check_id"] == str(new_check_id)
    assert state.data["feedback_usefulness"] is None
    assert state.data["feedback_check_id"] is None


@pytest.mark.parametrize("status", [CheckStatus.ok, CheckStatus.no_signal])
async def test_answerable_results_offer_the_feedback_keyboard(
    session, monkeypatch, status: CheckStatus
) -> None:
    settings = _settings()
    await _grant_consent(session, settings, language="ru")
    _stub_run_check(monkeypatch, status=status, check_id=uuid4())
    message = _Message(text="Пришлите код")

    await on_content(message, _State(), settings, _SessionFactory(session))

    assert message.replies[-1]["reply_markup"] is not None


@pytest.mark.parametrize(
    "status", [CheckStatus.safety_fallback, CheckStatus.rate_limited, CheckStatus.low_ocr]
)
async def test_non_answer_results_offer_no_feedback_keyboard(
    session, monkeypatch, status: CheckStatus
) -> None:
    """Rating a fallback or a refusal would collect meaningless signal."""

    settings = _settings()
    await _grant_consent(session, settings, language="ru")
    _stub_run_check(monkeypatch, status=status, check_id=uuid4())
    message = _Message(text="Пришлите код")

    await on_content(message, _State(), settings, _SessionFactory(session))

    assert message.replies[-1]["reply_markup"] is None


async def test_a_result_without_text_falls_back_to_the_unsupported_message(
    session, monkeypatch
) -> None:
    settings = _settings()
    await _grant_consent(session, settings, language="ru")
    _stub_run_check(monkeypatch, status=CheckStatus.ok, check_id=uuid4(), text=None)
    message = _Message(text="Пришлите код")

    await on_content(message, _State(), settings, _SessionFactory(session))

    assert message.last_reply == t("unsupported_input", "ru")
