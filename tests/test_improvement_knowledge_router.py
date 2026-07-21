"""T-01/T-05 acceptance: knowledge ceilings, router recall, health, and cost."""

from __future__ import annotations

from app.config import Settings
from app.engine import CheckInput, CheckStatus, InputType, Language, run_check
from app.engine.knowledge import KnowledgeBase, RetrievalResult, RouterResponse, retrieve_knowledge
from app.engine.knowledge.router import OpenAICompatibleKnowledgeRouter
from app.engine.knowledge.types import KnowledgeCard
from app.engine.llm import LLMResponse
from app.engine.llm.openai_compat import JSONCompletion
from app.engine.types import DraftOutput, Signal


class _Store:
    def __init__(self, cards: list[KnowledgeCard]) -> None:
        self.cards = cards

    def load(self, face_id: str) -> KnowledgeBase:
        return KnowledgeBase(version="test-v1", face=face_id, cards=tuple(self.cards))


class _Router:
    def __init__(self, response: RouterResponse | Exception) -> None:
        self.response = response
        self.calls = 0
        self.minimized_text = None

    async def route(self, **kwargs):
        self.calls += 1
        self.minimized_text = kwargs["minimized_text"]
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class _JSONProvider:
    def __init__(self, card_ids: list[str]) -> None:
        self.card_ids = card_ids
        self.calls: list[dict] = []

    async def complete_json(self, **kwargs) -> JSONCompletion:
        self.calls.append(kwargs)
        return JSONCompletion(
            payload={"card_ids": self.card_ids, "unmatched": False},
            input_tokens=7,
            output_tokens=3,
        )


class _AnswerProvider:
    async def analyze(self, **_kwargs) -> LLMResponse:
        return LLMResponse(
            draft=DraftOutput(
                red_flags=[],
                verify=["Проверьте сведения через независимый официальный канал."],
                ask=["Какие данные можно подтвердить независимо?"],
                addressed_rule_ids=[],
            ),
            input_tokens=20,
            output_tokens=10,
        )


def _card(index: int, *, alias: str = "shared cue") -> KnowledgeCard:
    return KnowledgeCard(
        id=f"family.test_{index}",
        face="family",
        version="v1",
        status="approved",
        reviewer="reviewer",
        retrieval_aliases={"ru": [alias]},
        mechanism=f"mechanism {index}",
        verify_steps=["verify"],
        questions=["ask"],
    )


def _settings(**overrides) -> Settings:
    values = {
        "telegram_token": "token",
        "database_url": "sqlite+aiosqlite:///:memory:",
        "app_hmac_secret": "test-secret",
        "llm_base_url": "https://example.invalid/v1",
        "llm_api_key": "key",
        "llm_model": "answer",
        "llm_in_rate_per_m": 1.0,
        "llm_out_rate_per_m": 2.0,
        "web_session_secret": "web-secret",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


async def test_router_is_not_called_when_deterministic_retrieval_already_succeeded() -> None:
    router = _Router(AssertionError("router call would be discarded"))
    result = await retrieve_knowledge(
        face_id="family",
        minimized_text="shared cue",
        rule_hits=[],
        signals=[],
        store=_Store([_card(index) for index in range(4)]),
        router=router,
    )

    assert router.calls == 0
    assert len(result.cards) == 3
    assert result.status == "ok"
    assert result.router_status == "not_used"


async def test_router_failure_and_invalid_ids_do_not_overwrite_retrieval_status() -> None:
    unavailable = await retrieve_knowledge(
        face_id="family",
        minimized_text="no cue",
        rule_hits=[],
        signals=[],
        store=_Store([_card(1)]),
        router=_Router(RuntimeError("down")),
    )
    invalid = await retrieve_knowledge(
        face_id="family",
        minimized_text="no cue",
        rule_hits=[],
        signals=[],
        store=_Store([_card(1)]),
        router=_Router(RouterResponse(card_ids=["invented.id"])),
    )

    assert unavailable.status == invalid.status == "empty"
    assert unavailable.router_status == "unavailable"
    assert invalid.router_status == "invalid_ids"
    assert invalid.cards == ()


async def test_signal_only_retrieval_selects_mandatory_card() -> None:
    card = _card(1, alias="never present")
    card.trigger_signal_kinds = ["link"]
    result = await retrieve_knowledge(
        face_id="family",
        minimized_text="no cue",
        rule_hits=[],
        signals=[Signal(kind="link")],
        store=_Store([card]),
    )

    assert result.knowledge_card_ids == ["family.test_1"]
    assert result.mode == "signal"
    assert result.status == "ok"


async def test_real_router_class_routes_inflected_russian_end_to_end_and_counts_cost() -> None:
    """Prove the router's wiring on an inflected phrase no alias matches.

    The provider is a fake returning a fixed ID, so this covers the plumbing —
    minimized text and the allowlist reach the model, the response is parsed and
    validated, and router tokens land in the cost. Whether a live model actually
    picks the right card for this phrasing is a model-quality question that only
    an eval against a real provider can answer.
    """

    json_provider = _JSONProvider(["family.authority_impersonation"])
    router = OpenAICompatibleKnowledgeRouter(json_provider)  # type: ignore[arg-type]
    result = await run_check(
        CheckInput(
            face="family",
            user_key="router-inflection",
            language=Language.ru,
            input_type=InputType.text,
            raw_text="Мне звонили, представились прокуратурой.",
        ),
        llm_provider=_AnswerProvider(),
        knowledge_router=router,
        settings=_settings(),
    )

    assert result.status == CheckStatus.no_signal
    assert result.rule_ids == []
    assert result.knowledge_card_ids == ["family.authority_impersonation"]
    assert result.retrieval_mode == "router"
    assert result.router_status == "ok"
    assert result.input_tokens == 27
    assert result.output_tokens == 13
    assert result.cost_usd == 0.000053
    assert "прокуратурой" in json_provider.calls[0]["user"]
    assert "family.authority_impersonation" in json_provider.calls[0]["user"]


async def test_router_receives_minimized_text_only() -> None:
    router = _Router(RouterResponse())
    raw_phone = "+998 90 123 45 67"
    result = await run_check(
        CheckInput(
            face="family",
            user_key="router-minimized",
            language=Language.ru,
            input_type=InputType.text,
            raw_text=f"A general situation; contact was {raw_phone}.",
        ),
        llm_provider=_AnswerProvider(),
        knowledge_router=router,
    )

    assert result.status == CheckStatus.no_signal
    assert router.minimized_text is not None
    assert "[PHONE]" in router.minimized_text
    assert raw_phone not in router.minimized_text


def test_router_is_off_by_default_and_has_separate_provider_config() -> None:
    settings = _settings()
    assert settings.knowledge_router_enabled is False
    assert settings.knowledge_router_base_url is None
    assert settings.knowledge_router_model is None


async def test_enabled_but_incomplete_router_config_degrades_to_answer_model() -> None:
    result = await run_check(
        CheckInput(
            face="family",
            user_key="router-config-down",
            language=Language.ru,
            input_type=InputType.text,
            raw_text="A general in-scope situation with no known cue.",
        ),
        llm_provider=_AnswerProvider(),
        settings=_settings(knowledge_router_enabled=True),
    )

    assert result.status == CheckStatus.no_signal
    assert result.retrieval_status == "empty"
    assert result.router_status == "unavailable"


def test_retrieval_result_defaults_keep_router_health_separate() -> None:
    result = RetrievalResult()
    assert result.status == "empty"
    assert result.router_status == "not_used"
