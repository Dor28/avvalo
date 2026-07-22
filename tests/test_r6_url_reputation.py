"""R6 acceptance: local hash-only URL reputation stage."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.config import Settings
from app.data.models import URLBlocklist
from app.engine import CheckInput, CheckStatus, InputType, Language, run_check
from app.engine.llm import LLMResponse
from app.engine.types import DraftOutput, RuleHit
from app.engine.url_reputation import (
    URLReputationMatch,
    hash_domain,
    normalize_domain,
    refresh_url_blocklist,
)
from app.engine.validate import validate


class _ReputationStore:
    def __init__(self, *, hit: bool) -> None:
        self.hit = hit
        self.calls: list[tuple[str, ...]] = []

    async def lookup(self, domain_hashes: tuple[str, ...]) -> list[URLReputationMatch]:
        self.calls.append(domain_hashes)
        if not self.hit:
            return []
        return [
            URLReputationMatch(
                domain_hash=domain_hashes[0],
                source="openphish",
                first_seen=datetime(2026, 7, 1, tzinfo=UTC),
            )
        ]


class _LLM:
    def __init__(self, draft: DraftOutput) -> None:
        self.draft = draft
        self.calls: list[dict] = []

    async def analyze(self, **kwargs) -> LLMResponse:
        self.calls.append(kwargs)
        return LLMResponse(draft=self.draft, input_tokens=10, output_tokens=5)


def _settings(*, enabled: bool) -> Settings:
    return Settings(
        _env_file=None,
        telegram_token="token",
        database_url="sqlite+aiosqlite:///:memory:",
        app_hmac_secret="test-secret",
        llm_base_url="https://example.invalid/v1",
        llm_api_key="key",
        llm_model="answer",
        web_session_secret="web-secret",
        url_reputation_enabled=enabled,
        urlhaus_feed_url="https://feeds.invalid/urlhaus",
        openphish_feed_url="https://feeds.invalid/openphish",
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("HTTPS://WWW.Example.COM/path", "example.com"),
        ("hxxps://Example[.]COM/login", "example.com"),
        ("https://xn--e1afmkfd.xn--p1ai/a", "пример.рф"),
        ("www.Example.com", "example.com"),
    ],
)
def test_domain_normalization_handles_scheme_www_case_and_idna(
    value: str, expected: str
) -> None:
    assert normalize_domain(value) == expected


@pytest.mark.parametrize(
    ("language", "line"),
    [
        (
            Language.uz_latn,
            "Havola OpenPhish ochiq fishing bloklistida 2026-07-01 "
            "sanasidan ko'rsatilgan.",
        ),
        (
            Language.ru,
            "Ссылка указана в публичном фишинговом блоклисте OpenPhish "
            "с 2026-07-01.",  # noqa: RUF001 - intentional Russian preposition
        ),
    ],
)
async def test_blocklist_hit_flows_through_shared_pipeline_without_raw_url(
    language: Language,
    line: str,
) -> None:
    raw_url = "https://payme-fake.example/login"
    store = _ReputationStore(hit=True)
    llm = _LLM(
        DraftOutput(
            red_flags=[line],
            verify=["Open the official service independently."],
            ask=["What can be confirmed through the official service?"],
            addressed_rule_ids=["shared.link.blocklisted"],
        )
    )

    result = await run_check(
        CheckInput(
                        user_key=f"r6-{language}",
            language=language,
            input_type=InputType.text,
            raw_text=raw_url,
        ),
        llm_provider=llm,
        url_reputation_store=store,
        settings=_settings(enabled=True),
    )

    assert result.status == CheckStatus.ok
    assert result.rule_ids == ["shared.link.blocklisted"]
    assert "public phishing blocklist" in llm.calls[0]["user"]
    assert "sources=openphish" in llm.calls[0]["user"]
    assert "listed_since=2026-07-01" in llm.calls[0]["user"]
    assert raw_url not in (result.text or "")
    assert "payme-fake.example" not in (result.text or "")
    assert line in (result.text or "")


async def test_no_hit_and_disabled_flag_are_noops() -> None:
    no_hit_store = _ReputationStore(hit=False)
    disabled_store = _ReputationStore(hit=True)
    draft = DraftOutput(
        red_flags=[],
        verify=["Use an independent official channel."],
        ask=["What can be verified independently?"],
        addressed_rule_ids=[],
    )
    no_hit = await run_check(
        CheckInput(
                        user_key="r6-no-hit",
            language=Language.ru,
            input_type=InputType.text,
            raw_text="https://ordinary.example/path",
        ),
        llm_provider=_LLM(draft),
        url_reputation_store=no_hit_store,
        settings=_settings(enabled=True),
    )
    disabled = await run_check(
        CheckInput(
                        user_key="r6-disabled",
            language=Language.ru,
            input_type=InputType.text,
            raw_text="https://listed.example/path",
        ),
        llm_provider=_LLM(draft),
        url_reputation_store=disabled_store,
        settings=_settings(enabled=False),
    )

    assert no_hit.rule_ids == []
    assert len(no_hit_store.calls) == 1
    assert disabled.rule_ids == []
    assert disabled_store.calls == []


def test_validator_requires_the_synthetic_fact_for_blocklist_synonyms() -> None:
    line = "The link appears in a public phishing list."
    draft = DraftOutput(
        red_flags=[line],
        verify=["Use an independent official channel."],
        ask=["What evidence is available through that channel?"],
        addressed_rule_ids=[],
    )

    unsupported = validate(draft, [], [], Language.ru)
    supported = validate(
        draft.model_copy(update={"addressed_rule_ids": ["shared.link.blocklisted"]}),
        [],
        [
            RuleHit(
                rule_id="shared.link.blocklisted",
                family="suspicious_link_qr",
                message_key="Public feed match.",
                severity=3,
            )
        ],
        Language.ru,
    )
    leaked_phone = validate(
        draft.model_copy(
            update={
                "red_flags": [f"{line} +998 90 123 45 67"],
                "addressed_rule_ids": ["shared.link.blocklisted"],
            }
        ),
        [],
        [
            RuleHit(
                rule_id="shared.link.blocklisted",
                family="suspicious_link_qr",
                message_key="Public feed match.",
                severity=3,
            )
        ],
        Language.ru,
    )

    assert unsupported.ok is False
    assert unsupported.reason == "unsupported URL blocklist claim"
    assert supported.ok is True
    assert leaked_phone.reason == "raw phone number leaked"


async def test_refresh_job_hashes_feeds_and_never_persists_raw_domains(
    session,
    tmp_path,
) -> None:
    own = tmp_path / "uz_phishing_domains.yaml"
    own.write_text("domains:\n  - mahalliy-phish.uz\n", encoding="utf-8")

    async def fetch(url: str) -> str:
        if "urlhaus" in url:
            return '"1","2026-07-01","https://Malware.Example/path","online"'
        return "https://phish.example/login\n"

    result = await refresh_url_blocklist(
        session,
        settings=_settings(enabled=True),
        fetcher=fetch,
        own_list_path=own,
        now=datetime(2026, 7, 19, tzinfo=UTC),
    )
    rows = (await session.execute(select(URLBlocklist))).scalars().all()

    assert result.entries == 3
    assert result.sources == 3
    assert {row.source for row in rows} == {"urlhaus", "openphish", "uz_local"}
    assert {row.domain_hash for row in rows} == {
        hash_domain("malware.example"),
        hash_domain("phish.example"),
        hash_domain("mahalliy-phish.uz"),
    }
    persisted = "\n".join(
        str(getattr(row, column.name))
        for row in rows
        for column in URLBlocklist.__table__.columns
    )
    assert "malware.example" not in persisted
    assert "phish.example" not in persisted


async def test_refresh_upsert_preserves_first_seen_and_updates_last_seen(
    session,
    tmp_path,
) -> None:
    own = tmp_path / "uz_phishing_domains.yaml"
    own.write_text("domains:\n  - mahalliy-phish.uz\n", encoding="utf-8")

    async def fetch(_url: str) -> str:
        return ""

    first = datetime(2026, 7, 18, tzinfo=UTC)
    second = datetime(2026, 7, 19, tzinfo=UTC)
    await refresh_url_blocklist(
        session,
        settings=_settings(enabled=True),
        fetcher=fetch,
        own_list_path=own,
        now=first,
    )
    await refresh_url_blocklist(
        session,
        settings=_settings(enabled=True),
        fetcher=fetch,
        own_list_path=own,
        now=second,
    )
    row = await session.get(
        URLBlocklist,
        (hash_domain("mahalliy-phish.uz"), "uz_local"),
    )

    assert row is not None
    assert row.first_seen.replace(tzinfo=UTC) == first
    assert row.last_seen.replace(tzinfo=UTC) == second


async def test_refresh_feed_failure_keeps_other_sources_available(session, tmp_path) -> None:
    own = tmp_path / "uz_phishing_domains.yaml"
    own.write_text("domains:\n  - mahalliy-phish.uz\n", encoding="utf-8")

    async def fetch(url: str) -> str:
        if "urlhaus" in url:
            raise TimeoutError("private provider detail")
        return "https://phish.example/login\n"

    result = await refresh_url_blocklist(
        session,
        settings=_settings(enabled=True),
        fetcher=fetch,
        own_list_path=own,
    )

    assert result.sources == 2
    assert result.entries == 2
