"""R3 opt-in minimized story capture tests."""

from types import SimpleNamespace

from sqlalchemy import select

from app.bot.handlers import on_feedback, on_story_callback, on_story_text
from app.bot.states import Onboarding, StoryCapture
from app.bot.texts import t
from app.config import Settings
from app.data import repo
from app.data.models import StorySubmission
from app.engine.faces import FACES
from app.privacy.user_key import derive_user_key
from tools import stories as stories_cli


def _settings(**overrides) -> Settings:
    values = {
        "telegram_token": "token",
        "database_url": "postgresql+asyncpg://avvalo:avvalo@localhost:5432/avvalo",
        "app_hmac_secret": "test-hmac-secret",
        "llm_base_url": "http://localhost:11434/v1",
        "llm_api_key": "ollama",
        "llm_model": "qwen2.5:7b-instruct",
        "web_session_secret": "test-web-session-secret",
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


class _FakeState:
    def __init__(self, data=None) -> None:
        self.data = dict(data or {})
        self.state = None

    async def get_data(self) -> dict:
        return dict(self.data)

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def set_data(self, data) -> None:
        self.data = dict(data)

    async def set_state(self, state) -> None:
        self.state = state

    async def clear(self) -> None:
        self.data = {}
        self.state = None


class _FakeBot:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send_message(self, chat_id, text, reply_markup=None) -> None:
        self.messages.append(
            {"chat_id": chat_id, "text": text, "reply_markup": reply_markup}
        )


class _FakeCallback:
    def __init__(self, data: str, *, bot: _FakeBot | None = None, user_id: int = 123) -> None:
        self.data = data
        self.bot = bot
        self.message = None
        self.from_user = SimpleNamespace(id=user_id)
        self.answers: list[str | None] = []

    async def answer(self, text=None, **_kwargs) -> None:
        self.answers.append(text)


class _FakeMessage:
    def __init__(self, text: str | None = None, *, user_id: int = 123) -> None:
        self.text = text
        self.caption = None
        self.photo = None
        self.bot = None
        self.from_user = SimpleNamespace(id=user_id)
        self.messages: list[dict] = []

    async def answer(self, text, reply_markup=None) -> None:
        self.messages.append({"text": text, "reply_markup": reply_markup})


async def test_story_flow_stores_only_after_publish_and_forwards_operator(session) -> None:
    settings = _settings(operator_alert_chat_id=777)
    factory = _SessionFactory(session)
    bot = _FakeBot()
    check_id = await repo.record_check_event(
        session,
        user_key="story-user",
        face="family",
        input_type="text",
        language="ru",
        status="ok",
    )
    await session.commit()
    state = _FakeState({"language": "ru", "last_check_id": str(check_id)})

    await on_feedback(
        _FakeCallback("feedback:usefulness:yes", bot=bot),
        state,
        factory,
        FACES["family"],
    )

    assert state.data["story_check_id"] == str(check_id)
    assert any(t("story_invite", "ru") in message["text"] for message in bot.messages)

    await on_story_callback(
        _FakeCallback("story:start", bot=bot),
        state,
        settings,
        factory,
        FACES["family"],
    )
    assert state.state == StoryCapture.awaiting_story

    story_message = _FakeMessage(
        "Murod Karimov wrote from +998 90 123 45 67 and asked for SMS kod 123456."
    )
    await on_story_text(story_message, state, settings, FACES["family"])

    assert state.state == StoryCapture.awaiting_publish
    preview = story_message.messages[-1]["text"]
    assert "[PHONE]" in preview
    assert "[CODE]" in preview
    assert "+998" not in preview
    assert "123456" not in preview
    assert (await session.execute(select(StorySubmission))).scalars().all() == []

    await on_story_callback(
        _FakeCallback("story:publish", bot=bot),
        state,
        settings,
        factory,
        FACES["family"],
    )

    stories = (await session.execute(select(StorySubmission))).scalars().all()
    assert len(stories) == 1
    stored = stories[0]
    assert stored.status == "submitted"
    assert "[PHONE]" in stored.minimized_text
    assert "[CODE]" in stored.minimized_text
    assert "+998" not in stored.minimized_text
    assert "123456" not in stored.minimized_text
    assert "story_raw_text" not in state.data
    operator_messages = [message for message in bot.messages if message["chat_id"] == 777]
    assert len(operator_messages) == 1
    assert stored.minimized_text in operator_messages[0]["text"]
    assert "+998" not in operator_messages[0]["text"]


async def test_story_daily_limit_blocks_new_capture(session) -> None:
    settings = _settings(story_daily_limit=1)
    factory = _SessionFactory(session)
    user_key = derive_user_key(123, secret=settings.app_hmac_secret.get_secret_value())
    await repo.store_story(
        session,
        user_key=user_key,
        face="family",
        language="ru",
        raw_text="Already submitted one minimized story.",
    )
    await session.commit()
    state = _FakeState({"language": "ru", "story_check_id": "check"})
    bot = _FakeBot()

    await on_story_callback(
        _FakeCallback("story:start", bot=bot),
        state,
        settings,
        factory,
        FACES["family"],
    )

    assert state.state == Onboarding.ready
    assert "story_raw_text" not in state.data
    assert any(t("story_limit_reached", "ru") in message["text"] for message in bot.messages)


async def test_stories_cli_lists_and_approves(session, capsys) -> None:
    story = await repo.store_story(
        session,
        user_key="cli-user",
        face="family",
        language="ru",
        raw_text="A minimized story for founder review.",
    )
    await session.commit()
    factory = _SessionFactory(session)

    assert await stories_cli.run(["list"], session_factory=factory) == 0
    listed = capsys.readouterr().out
    assert str(story.id) in listed
    assert "founder review" in listed

    assert await stories_cli.run(["approve", str(story.id)], session_factory=factory) == 0
    approved = await session.get(StorySubmission, story.id)
    assert approved is not None
    assert approved.status == "approved"
    assert approved.reviewed_ts is not None
