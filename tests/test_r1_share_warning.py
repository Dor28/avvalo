"""R1 share-warning tests for the content-free Telegram share loop."""

import re
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from pydantic import SecretStr

from app.bot.handlers import on_share
from app.bot.keyboards import BOT_LINK
from app.bot.texts import t
from app.data import repo
from app.engine.format import share_summary
from app.engine.rules import run_rules
from app.engine.types import Language

_LONG_DIGIT_RE = re.compile(r"\d{5,}")
_URL_RE = re.compile(r"https?://[^\s]+")
_SETTINGS = SimpleNamespace(app_hmac_secret=SecretStr("test-share-hmac-secret"))


def test_share_summary_is_content_free_for_all_golden_fixtures(golden) -> None:
    for case in golden():
        rule_hits, _signals = run_rules(case["input"])
        rule_ids = [hit.rule_id for hit in rule_hits]
        for language in Language:
            summary = share_summary(rule_ids, language)
            _assert_content_free(summary, submitted_text=case["input"])
            assert BOT_LINK in summary


def test_share_summary_has_generic_copy_when_no_rules_fire() -> None:
    summary = share_summary([], Language.ru)

    _assert_content_free(summary, submitted_text="")
    assert "Найденные признаки" not in summary
    assert BOT_LINK in summary


async def test_share_callback_rebuilds_summary_and_logs_click(session, monkeypatch) -> None:
    callback = _FakeCallback(data="pending", bot=_FakeBot())
    check_id = await repo.record_check_event(
        session,
        user_key=_share_user_key(callback.from_user.id),
        input_type="text",
        language="ru",
        status="ok",
        rule_ids=["fs.credential.otp", "fs.urgency.deadline"],
    )
    await session.commit()
    events = []
    monkeypatch.setattr(
        "app.bot.handlers.log_event",
        lambda name, **fields: events.append((name, fields)),
    )

    bot = callback.bot
    callback.data = f"share:{check_id}"

    await on_share(callback, _FakeState(language="ru"), _SETTINGS, _SessionFactory(session))

    assert callback.answers == [(None,)]
    assert events == [("share_clicked", {"language": "ru"})]
    assert len(bot.messages) == 1
    sent = bot.messages[0]
    assert sent["chat_id"] == 123
    assert sent["text"] == share_summary(
        ["fs.credential.otp", "fs.urgency.deadline"], Language.ru
    )
    button = sent["reply_markup"].inline_keyboard[0][0]
    query = parse_qs(urlparse(button.url).query)
    assert query["url"] == [BOT_LINK]
    assert query["text"] == [sent["text"]]


async def test_share_callback_rejects_check_owned_by_another_user(session, monkeypatch) -> None:
    check_id = await repo.record_check_event(
        session,
        user_key=_share_user_key(999),
        input_type="text",
        language="ru",
        status="ok",
        rule_ids=["fs.credential.otp"],
    )
    await session.commit()
    events = []
    monkeypatch.setattr(
        "app.bot.handlers.log_event",
        lambda name, **fields: events.append((name, fields)),
    )
    bot = _FakeBot()
    callback = _FakeCallback(data=f"share:{check_id}", bot=bot)

    await on_share(callback, _FakeState(language="ru"), _SETTINGS, _SessionFactory(session))

    assert callback.answers == [(t("share_expired", "ru"),)]
    assert bot.messages == []
    assert events == []


async def test_share_callback_answers_gracefully_for_unknown_check_id(
    session, monkeypatch
) -> None:
    events = []
    monkeypatch.setattr(
        "app.bot.handlers.log_event",
        lambda name, **fields: events.append((name, fields)),
    )
    bot = _FakeBot()
    callback = _FakeCallback(data=f"share:{uuid4()}", bot=bot)

    await on_share(callback, _FakeState(language="ru"), _SETTINGS, _SessionFactory(session))

    assert callback.answers == [(t("share_expired", "ru"),)]
    assert bot.messages == []
    assert events == []


def _assert_content_free(summary: str, *, submitted_text: str) -> None:
    if submitted_text:
        assert submitted_text not in summary
    assert not _LONG_DIGIT_RE.search(summary)
    assert "@@" not in summary
    assert "@" not in summary
    assert "+998" not in summary
    urls = {url.rstrip(".,)") for url in _URL_RE.findall(summary)}
    assert urls <= {BOT_LINK}


def _share_user_key(user_id: int) -> str:
    from app.privacy.user_key import derive_user_key

    return derive_user_key(user_id, secret=_SETTINGS.app_hmac_secret.get_secret_value())


class _SessionFactory:
    def __init__(self, session) -> None:
        self.session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, _exc_type, _exc, _tb) -> None:
        return None


class _FakeBot:
    def __init__(self) -> None:
        self.messages = []

    async def send_message(self, chat_id, text, reply_markup=None) -> None:
        self.messages.append(
            {"chat_id": chat_id, "text": text, "reply_markup": reply_markup}
        )


class _FakeCallback:
    def __init__(self, *, data: str, bot: _FakeBot) -> None:
        self.data = data
        self.bot = bot
        self.from_user = SimpleNamespace(id=123)
        self.message = None
        self.answers = []

    async def answer(self, text=None) -> None:
        self.answers.append((text,))


class _FakeState:
    def __init__(self, *, language: str) -> None:
        self.language = language

    async def get_data(self) -> dict[str, str]:
        return {"language": self.language}
