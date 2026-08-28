"""Red-flag provenance and filler-bullet removal (PIPELINE_V2 §3, §5)."""

import pytest

from app.config import Settings
from app.engine import CheckInput, CheckStatus, InputType, Language, run_check
from app.engine.format import format_result
from app.engine.llm import LLMResponse
from app.engine.llm.prompt import draft_output_schema
from app.engine.types import DraftOutput, Evidence, RuleHit, Signal
from app.engine.validate import ValidationReason, validate

_OTP_HIT = RuleHit(
    rule_id="fs.credential.otp",
    family="credential_theft",
    message_key="otp_request",
    severity=3,
)
_LOW_HIT = RuleHit(
    rule_id="fs.link.shortened",
    family="suspicious_link_qr",
    message_key="shortened",
    severity=1,
)


def _draft(**overrides) -> DraftOutput:
    base = {
        "red_flags": [],
        "pattern": "Authority pressure and urgency.",
        "verify": ["Open the bank app yourself before acting."],
        "ask": ["Ask which official channel shows this request."],
        "addressed_rule_ids": [],
    }
    return DraftOutput(**{**base, **overrides})


def _settings(**overrides) -> Settings:
    return Settings(
        _env_file=None,
        telegram_token="token",
        database_url="postgresql+asyncpg://avvalo:avvalo@localhost:5432/avvalo",
        app_hmac_secret="test-hmac-secret",
        llm_base_url="http://localhost:11434/v1",
        llm_api_key="ollama",
        llm_model="qwen2.5:7b-instruct",
        web_session_secret="test-web-session-secret",
        **overrides,
    )


# --------------------------------------------------------------------------
# Grounding
# --------------------------------------------------------------------------


def test_red_flag_naming_a_detected_rule_is_kept() -> None:
    draft = _draft(
        red_flags=[Evidence(text="A one-time code is requested.", source_id="fs.credential.otp")],
        addressed_rule_ids=["fs.credential.otp"],
    )

    result = validate(draft, [], [_OTP_HIT], Language.ru, require_grounding=True)

    assert result.ok
    assert [flag.text for flag in result.draft.red_flags] == ["A one-time code is requested."]
    assert result.dropped_ungrounded == 0
    assert result.grounding_unsupported is False


def test_red_flag_may_cite_a_signal_kind_or_a_card_id() -> None:
    draft = _draft(
        red_flags=[
            Evidence(text="The link hides its destination.", source_id="link_shortened"),
            Evidence(text="Secrets are requested in chat.", source_id="family.credential_theft"),
        ]
    )

    result = validate(
        draft,
        [Signal(kind="link_shortened", note="shortener")],
        [],
        Language.ru,
        knowledge_card_ids=["family.credential_theft"],
        require_grounding=True,
    )

    assert result.ok
    assert len(result.draft.red_flags) == 2
    assert result.dropped_ungrounded == 0


def test_red_flag_citing_an_undetected_id_is_dropped() -> None:
    draft = _draft(
        red_flags=[
            Evidence(text="A one-time code is requested.", source_id="fs.credential.otp"),
            Evidence(text="The seller demands prepayment.", source_id="fs.payment.upfront"),
        ],
        addressed_rule_ids=["fs.credential.otp"],
    )

    result = validate(draft, [], [_OTP_HIT], Language.ru, require_grounding=True)

    assert result.ok
    assert [flag.text for flag in result.draft.red_flags] == ["A one-time code is requested."]
    assert result.dropped_ungrounded == 1


def test_dropping_every_required_red_flag_rejects_with_the_grounding_reason() -> None:
    """A severity-3 hit needs a red flag; losing them all must not ship silently."""

    draft = _draft(
        red_flags=[Evidence(text="Something looks wrong.", source_id="fs.invented.rule")],
        addressed_rule_ids=["fs.credential.otp"],
    )

    result = validate(draft, [], [_OTP_HIT], Language.ru, require_grounding=True)

    assert not result.ok
    assert result.reason is ValidationReason.UNGROUNDED_RED_FLAG
    assert result.dropped_ungrounded == 1


def test_low_severity_hit_survives_losing_its_only_red_flag() -> None:
    """Severity 1 grounds the prompt but never forces a flag, so dropping is safe."""

    draft = _draft(
        red_flags=[Evidence(text="Something looks wrong.", source_id="fs.invented.rule")]
    )

    result = validate(draft, [], [_LOW_HIT], Language.ru, require_grounding=True)

    assert result.ok
    assert result.draft.red_flags == []


def test_grounding_is_off_by_default() -> None:
    draft = _draft(red_flags=[Evidence(text="Unattributed warning.", source_id="nonsense")])

    result = validate(draft, [], [_LOW_HIT], Language.ru)

    assert result.ok
    assert [flag.text for flag in result.draft.red_flags] == ["Unattributed warning."]


# --------------------------------------------------------------------------
# Compatibility floor
# --------------------------------------------------------------------------


def test_a_model_that_never_cites_keeps_its_flags_and_is_reported() -> None:
    """A host that ignores the nested schema must degrade, not empty every answer."""

    draft = _draft(
        red_flags=[Evidence(text="A one-time code is requested."), Evidence(text="Urgency.")],
        addressed_rule_ids=["fs.credential.otp"],
    )

    result = validate(draft, [], [_OTP_HIT], Language.ru, require_grounding=True)

    assert result.ok
    assert len(result.draft.red_flags) == 2
    assert result.grounding_unsupported is True
    assert result.dropped_ungrounded == 0


def test_one_cited_flag_makes_enforcement_strict_for_the_rest() -> None:
    """Citing once proves the model understands the field, so bare flags are omissions."""

    draft = _draft(
        red_flags=[
            Evidence(text="A one-time code is requested.", source_id="fs.credential.otp"),
            Evidence(text="Vague extra claim."),
        ],
        addressed_rule_ids=["fs.credential.otp"],
    )

    result = validate(draft, [], [_OTP_HIT], Language.ru, require_grounding=True)

    assert result.ok
    assert [flag.text for flag in result.draft.red_flags] == ["A one-time code is requested."]
    assert result.dropped_ungrounded == 1
    assert result.grounding_unsupported is False


def test_bare_string_red_flags_still_parse() -> None:
    """The wire contract changed; a host sending the old shape must not 500."""

    draft = DraftOutput.model_validate({"red_flags": ["Plain string flag."]})

    assert draft.red_flags == [Evidence(text="Plain string flag.", source_id="")]


def test_validator_survives_strings_injected_past_field_validation() -> None:
    """``model_copy(update=…)`` bypasses validators; the safety boundary must hold."""

    draft = _draft().model_copy(update={"red_flags": ["Injected raw string."]})

    result = validate(draft, [], [], Language.ru, require_grounding=True)

    assert result.ok
    assert [flag.text for flag in result.draft.red_flags] == ["Injected raw string."]


# --------------------------------------------------------------------------
# Filler blocklist
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bullet",
    [
        "Будьте осторожны.",
        "будьте бдительны",
        "Соблюдайте осторожность в интернете.",
        "Всегда проверяйте официальные источники.",
        "Ehtiyot bo'ling.",
        "Ehtiyot bo‘ling!",
        "Hushyor bo'ling.",
        "Doimo rasmiy manbalarni tekshiring.",
        "Эҳтиёт бўлинг.",
        "Be careful online.",
        "Exercise caution.",
    ],
)
def test_whole_bullet_filler_is_dropped(bullet: str) -> None:
    draft = _draft(red_flags=[Evidence(text=bullet, source_id="fs.link.shortened")])

    result = validate(draft, [], [_LOW_HIT], Language.ru)

    assert result.draft.red_flags == []
    assert result.dropped_filler == 1


@pytest.mark.parametrize(
    "bullet",
    [
        "Будьте осторожны: у вас просят код из СМС, которым никто не должен владеть.",
        "Ehtiyot bo'ling — sizdan SMS kodni so'rashmoqda.",
        "Откройте приложение банка самостоятельно и проверьте перевод.",
    ],
)
def test_a_concrete_bullet_containing_a_stock_phrase_is_kept(bullet: str) -> None:
    """The filter removes content-free bullets, it does not police style."""

    draft = _draft(red_flags=[Evidence(text=bullet, source_id="fs.link.shortened")])

    result = validate(draft, [], [_LOW_HIT], Language.ru)

    assert [flag.text for flag in result.draft.red_flags] == [bullet]
    assert result.dropped_filler == 0


def test_filler_verify_bullet_is_dropped_when_a_real_one_survives() -> None:
    draft = _draft(
        verify=["Будьте осторожны.", "Откройте приложение банка самостоятельно."],
    )

    result = validate(draft, [], [], Language.ru)

    assert result.draft.verify == ["Откройте приложение банка самостоятельно."]


def test_the_last_verify_bullet_survives_even_as_filler() -> None:
    """Vague advice beats an empty block, which would return fixed fallback copy."""

    draft = _draft(verify=["Будьте осторожны."])

    result = validate(draft, [], [], Language.ru)

    assert result.ok
    assert result.draft.verify == ["Будьте осторожны."]
    assert result.reason is not ValidationReason.VERIFY_BLOCK_EMPTY


def test_filtering_runs_before_truncation_so_the_best_three_survive() -> None:
    draft = _draft(
        red_flags=[
            Evidence(text="Будьте осторожны.", source_id="fs.link.shortened"),
            Evidence(text="First real warning.", source_id="fs.link.shortened"),
            Evidence(text="Second real warning.", source_id="fs.link.shortened"),
            Evidence(text="Third real warning.", source_id="fs.link.shortened"),
        ]
    )

    result = validate(draft, [], [_LOW_HIT], Language.ru, require_grounding=True)

    assert [flag.text for flag in result.draft.red_flags] == [
        "First real warning.",
        "Second real warning.",
        "Third real warning.",
    ]


# --------------------------------------------------------------------------
# Rendering and schema
# --------------------------------------------------------------------------


def test_source_ids_are_never_rendered_to_the_user() -> None:
    draft = _draft(
        red_flags=[Evidence(text="A one-time code is requested.", source_id="fs.credential.otp")]
    )

    rendered = format_result(draft, Language.ru)

    assert "A one-time code is requested." in rendered
    assert "fs.credential.otp" not in rendered


def test_schema_inlines_evidence_and_requires_attribution() -> None:
    """Not every OpenAI-compatible host resolves ``$defs``; an unresolved ref
    would silently hand the model an unconstrained array."""

    schema = draft_output_schema()

    assert "$defs" not in schema
    items = schema["properties"]["red_flags"]["items"]
    assert items["type"] == "object"
    assert set(items["required"]) == {"text", "source_id"}
    assert "$ref" not in str(schema)


# --------------------------------------------------------------------------
# End to end
# --------------------------------------------------------------------------


class _FakeLLM:
    def __init__(self, draft: DraftOutput) -> None:
        self.draft = draft
        self.calls = 0

    async def analyze(self, **kwargs) -> LLMResponse:
        self.calls += 1
        return LLMResponse(draft=self.draft, input_tokens=10, output_tokens=5)


async def test_pipeline_drops_an_ungrounded_flag_when_grounding_is_enabled(session) -> None:
    llm = _FakeLLM(
        _draft(
            red_flags=[
                Evidence(text="A one-time code is requested.", source_id="fs.credential.otp"),
                Evidence(text="Invented extra claim.", source_id="fs.not.detected"),
            ],
            addressed_rule_ids=["fs.credential.otp"],
        )
    )

    result = await run_check(
        CheckInput(
            user_key="grounding-user",
            language=Language.uz_latn,
            input_type=InputType.text,
            raw_text="Bank xizmatidanmiz. SMS orqali kelgan 6 xonali kodni yuboring.",
        ),
        session=session,
        llm_provider=llm,
        settings=_settings(answer_grounding_enabled=True),
    )
    await session.commit()

    assert result.status is CheckStatus.ok
    assert "Invented extra claim." not in (result.text or "")
    assert "fs.not.detected" not in (result.text or "")


def test_grounding_is_enabled_by_default_and_documented() -> None:
    """The flag exists for rollback; the shipped default must be enforcement on."""

    from pathlib import Path

    assert _settings().answer_grounding_enabled is True
    env_example = Path(__file__).resolve().parents[1] / ".env.example"
    assert "ANSWER_GROUNDING_ENABLED" in env_example.read_text(encoding="utf-8")
