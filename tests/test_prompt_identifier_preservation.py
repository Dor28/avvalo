"""Prompt-only name/URL preservation and provider privacy controls."""

import json
from types import SimpleNamespace

from app.engine import CheckInput, CheckStatus, InputType, Language, run_check
from app.engine.knowledge import KnowledgeBase, RouterResponse
from app.engine.llm import LLMResponse, OpenAICompatibleProvider
from app.engine.llm.prompt import draft_output_schema
from app.engine.minimize import minimize
from app.engine.types import DraftOutput
from tests.support import addressed_rule_ids


class EmptyKnowledgeStore:
    def load(self) -> KnowledgeBase:
        return KnowledgeBase(version="prompt-privacy-test-v1", cards=())


class CapturingRouter:
    def __init__(self) -> None:
        self.minimized_text: str | None = None

    async def route(self, **kwargs) -> RouterResponse:
        self.minimized_text = kwargs["minimized_text"]
        return RouterResponse()


class CapturingAnswerProvider:
    def __init__(self) -> None:
        self.user_prompt = ""

    async def analyze(self, **kwargs) -> LLMResponse:
        self.user_prompt = kwargs["user"]
        return LLMResponse(
            draft=DraftOutput(
                red_flags=["The message asks the reader to open a submitted link."],
                pattern="A link is presented as part of the situation.",
                verify=["Find the expected service through an independent channel."],
                ask=["Ask what verifiable process requires this link."],
                addressed_rule_ids=addressed_rule_ids(kwargs["user"]),
            ),
            input_tokens=20,
            output_tokens=10,
        )


class FakeCompletions:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(
                            {
                                "red_flags": ["One warning sign."],
                                "verify": ["Check independently."],
                                "ask": ["Ask a control question."],
                            }
                        )
                    )
                )
            ],
            usage=SimpleNamespace(prompt_tokens=12, completion_tokens=4),
        )


class FakeOpenAIClient:
    def __init__(self) -> None:
        self.completions = FakeCompletions()
        self.chat = SimpleNamespace(completions=self.completions)


def test_answer_view_preserves_full_names_and_urls_but_not_other_protected_values() -> None:
    full_url = (
        "https://example.uz/pay?card=8600123412345678&phone=+998901234567"
    )
    raw = (
        "Aziz Karimov, tel +998 90 123 45 67, karta 8600 1234 1234 5678, "
        "email support@bank.example, pasport AB1234567, SMS kod 123456, "
        f"parol: private-secret. Havola {full_url}"
    )

    strict = minimize(raw)
    answer_view = minimize(raw, preserve_names=True, preserve_urls=True)

    assert "Aziz Karimov" not in strict
    assert full_url not in strict
    assert "[NAME]" in strict
    assert "[LINK]" in strict

    assert "Aziz Karimov" in answer_view
    assert full_url in answer_view
    for raw_value in (
        "+998 90 123 45 67",
        "8600 1234 1234 5678",
        "support@bank.example",
        "AB1234567",
        "private-secret",
    ):
        assert raw_value not in answer_view
    assert "SMS kod 123456" not in answer_view
    for token in ("[PHONE]", "[CARD]", "[EMAIL]", "[PASSPORT]", "[CODE]", "[SECRET]"):
        assert token in answer_view


async def test_only_answer_model_receives_submitted_name_and_full_url() -> None:
    full_url = "https://example.uz/request?id=8600123412345678"
    raw = f"Aziz Karimov yozdi. Havola: {full_url}"
    router = CapturingRouter()
    answer_provider = CapturingAnswerProvider()

    result = await run_check(
        CheckInput(
            user_key="prompt-privacy-boundary",
            language=Language.uz_latn,
            input_type=InputType.text,
            raw_text=raw,
        ),
        llm_provider=answer_provider,
        knowledge_store=EmptyKnowledgeStore(),
        knowledge_router=router,
    )

    assert result.status == CheckStatus.ok
    assert "Aziz Karimov" in answer_provider.user_prompt
    assert full_url in answer_provider.user_prompt
    assert router.minimized_text is not None
    assert "Aziz Karimov" not in router.minimized_text
    assert full_url not in router.minimized_text
    assert "[NAME]" in router.minimized_text
    assert "[LINK]" in router.minimized_text


async def test_openrouter_requests_zero_retention_and_denies_data_collection() -> None:
    client = FakeOpenAIClient()
    provider = OpenAICompatibleProvider(
        base_url="https://openrouter.ai/api/v1",
        api_key="test-key",
        model="test-model",
        client=client,
    )

    await provider.analyze(
        system="system",
        user="user",
        schema=draft_output_schema(),
        max_output_tokens=100,
    )

    assert client.completions.calls[0]["extra_body"] == {
        "provider": {"zdr": True, "data_collection": "deny"}
    }


async def test_openrouter_request_disables_reasoning_when_configured() -> None:
    """Reasoning tokens are spent from max_tokens and truncate the JSON draft.

    Measured on deepseek-v4-flash: 519 of 600 completion tokens went to
    reasoning, so the draft was cut mid-object and failed to parse.
    """

    client = FakeOpenAIClient()
    provider = OpenAICompatibleProvider(
        base_url="https://openrouter.ai/api/v1",
        api_key="test-key",
        model="test-model",
        reasoning_effort="none",
        client=client,
    )

    await provider.analyze(
        system="system",
        user="user",
        schema=draft_output_schema(),
        max_output_tokens=100,
    )

    extra_body = client.completions.calls[0]["extra_body"]
    assert extra_body["reasoning"] == {"effort": "none"}
    # The privacy constraint must survive alongside it.
    assert extra_body["provider"] == {"zdr": True, "data_collection": "deny"}


async def test_openrouter_request_omits_reasoning_when_unset() -> None:
    client = FakeOpenAIClient()
    provider = OpenAICompatibleProvider(
        base_url="https://openrouter.ai/api/v1",
        api_key="test-key",
        model="test-model",
        client=client,
    )

    await provider.analyze(
        system="system",
        user="user",
        schema=draft_output_schema(),
        max_output_tokens=100,
    )

    assert "reasoning" not in client.completions.calls[0]["extra_body"]


async def test_non_openrouter_provider_request_is_unchanged() -> None:
    client = FakeOpenAIClient()
    provider = OpenAICompatibleProvider(
        base_url="http://localhost:11434/v1",
        api_key="ollama",
        model="test-model",
        client=client,
    )

    await provider.analyze(
        system="system",
        user="user",
        schema=draft_output_schema(),
        max_output_tokens=100,
    )

    assert "extra_body" not in client.completions.calls[0]
