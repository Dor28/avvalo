"""Regression tests for the second review-fix batch.

Covers:
- #4  DAILY_LIMIT_* settings actually drive the per-face daily limit.
- #5  the Telegram content handler builds a CheckInput; feedback keyboard is
      localized.
- #6  the web session cookie honors the configured Secure flag.
- #7  record_feedback is idempotent (re-answering does not raise).
- #8  usefulness feedback can be saved before next-action feedback.
"""

from starlette.responses import Response

from app.bot.handlers import _build_check_input
from app.bot.keyboards import post_check_keyboard
from app.bot.texts import t
from app.config import Settings
from app.data import repo
from app.data.models import Feedback
from app.engine import CheckInput, CheckStatus, InputType, Language, run_check
from app.engine.faces import FACES
from app.engine.llm import LLMResponse
from app.engine.types import DraftOutput
from app.web.session import WebSession, set_web_session_cookie


def _settings(**overrides) -> Settings:
    values = {
        "telegram_token": "bot-token",
        "database_url": "postgresql+asyncpg://avvalo:avvalo@localhost:5432/avvalo",
        "app_hmac_secret": "test-hmac-secret",
        "llm_base_url": "http://localhost:11434/v1",
        "llm_api_key": "ollama",
        "llm_model": "qwen2.5:7b-instruct",
        "web_session_secret": "test-web-session-secret",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


class _OkLLM:
    async def analyze(self, **_kwargs) -> LLMResponse:
        return LLMResponse(
            draft=DraftOutput(
                red_flags=["The message asks for a one-time code."],
                verify=["Open the official app yourself."],
                ask=["Which official channel shows this request?"],
            ),
            input_tokens=10,
            output_tokens=5,
        )


# --- #4: configured daily limit drives enforcement -------------------------

async def test_configured_daily_limit_overrides_face_default(session) -> None:
    settings = _settings(daily_limit_family=2)  # default would be 5
    check_input = CheckInput(
        face="family", user_key="cfg", language=Language.ru,
        input_type=InputType.text, raw_text="Bank xavfsizlik xizmati. SMS kodni yuboring.",
    )
    statuses = []
    for _ in range(3):
        result = await run_check(
            check_input, session=session, settings=settings, llm_provider=_OkLLM()
        )
        statuses.append(result.status)
    assert statuses == [CheckStatus.ok, CheckStatus.ok, CheckStatus.rate_limited]


def test_settings_daily_limit_for_maps_faces() -> None:
    settings = _settings(daily_limit_family=7, daily_limit_merchants=11)
    assert settings.daily_limit_for("family") == 7
    assert settings.daily_limit_for("merchants") == 11
    assert settings.daily_limit_for("unknown") is None


# --- #5: content handler input building + localized keyboard ----------------

class _FakeMessage:
    def __init__(self, *, text=None, caption=None, photo=None, bot=None) -> None:
        self.text = text
        self.caption = caption
        self.photo = photo
        self.bot = bot


async def test_build_check_input_from_text() -> None:
    result = await _build_check_input(
        _FakeMessage(text="Salom, bu xabarni tekshiring"),
        face=FACES["family"], user_key="u", language="ru",
    )
    assert result is not None
    assert result.input_type is InputType.text
    assert result.raw_text == "Salom, bu xabarni tekshiring"
    assert result.language is Language.ru


async def test_build_check_input_rejects_unsupported_message() -> None:
    result = await _build_check_input(
        _FakeMessage(),  # no text, no caption, no photo (e.g. a sticker)
        face=FACES["family"], user_key="u", language="uz_latn",
    )
    assert result is None


def test_post_check_keyboard_is_localized_and_keeps_callbacks() -> None:
    kb = post_check_keyboard("ru")
    labels = [b.text for row in kb.inline_keyboard for b in row]
    callbacks = [b.callback_data for row in kb.inline_keyboard for b in row if b.callback_data]
    assert t("fb_useful", "ru") in labels and t("fb_verify", "ru") in labels
    assert t("fb_share", "ru") in labels
    assert "feedback:usefulness:yes" in callbacks
    assert "feedback:next_action:delay_stop" in callbacks


def test_post_check_keyboard_uses_share_callback_when_check_id_exists() -> None:
    kb = post_check_keyboard("ru", "11111111-1111-4111-8111-111111111111")
    buttons = [b for row in kb.inline_keyboard for b in row]
    share = next(b for b in buttons if b.text == t("fb_share", "ru"))
    assert share.callback_data == "share:11111111-1111-4111-8111-111111111111"
    assert share.url is None


# --- #6: cookie Secure flag --------------------------------------------------

def test_session_cookie_secure_flag_is_configurable() -> None:
    ws = WebSession(user_key="k", signed_id="payload.sig", is_new=True)

    secure_resp = Response()
    set_web_session_cookie(secure_resp, ws, secure=True)
    assert "Secure" in secure_resp.headers["set-cookie"]

    plain_resp = Response()
    set_web_session_cookie(plain_resp, ws, secure=False)
    assert "Secure" not in plain_resp.headers["set-cookie"]


# --- #7: idempotent feedback -------------------------------------------------

async def test_record_feedback_is_idempotent(session) -> None:
    check_id = await repo.record_check_event(
        session, user_key="fb", face="family", input_type="text", language="ru", status="ok"
    )
    await repo.record_feedback(session, check_id=check_id, usefulness="yes", next_action="verify")
    # Re-answering must not raise a duplicate-key error; last answer wins.
    await repo.record_feedback(
        session, check_id=check_id, usefulness="partly", next_action="continue"
    )
    await session.commit()

    row = await session.get(Feedback, check_id)
    assert row is not None
    assert row.usefulness == "partly"
    assert row.next_action == "continue"


async def test_record_feedback_accepts_usefulness_before_next_action(session) -> None:
    check_id = await repo.record_check_event(
        session, user_key="fb-partial", face="family",
        input_type="text", language="ru", status="ok",
    )
    await repo.record_feedback(session, check_id=check_id, usefulness="yes")
    await repo.record_feedback(session, check_id=check_id, usefulness="yes", next_action="verify")
    await session.commit()

    row = await session.get(Feedback, check_id)
    assert row is not None
    assert row.usefulness == "yes"
    assert row.next_action == "verify"


async def test_usefulness_update_does_not_clear_next_action(session) -> None:
    check_id = await repo.record_check_event(
        session, user_key="fb-preserve", face="family",
        input_type="text", language="ru", status="ok",
    )
    await repo.record_feedback(session, check_id=check_id, usefulness="yes", next_action="verify")
    await repo.record_feedback(session, check_id=check_id, usefulness="partly")
    await session.commit()

    row = await session.get(Feedback, check_id)
    assert row is not None
    assert row.usefulness == "partly"
    assert row.next_action == "verify"
