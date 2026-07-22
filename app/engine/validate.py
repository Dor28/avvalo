"""Deterministic safety validation for LLM drafts (§9).

``addressed_rule_ids`` is a language-independent floor for rule preservation:
it catches silently dropped authoritative facts, but a model declaring an ID is
not proof that its wording explained that fact well.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from app.engine.types import DraftOutput, Language, RuleHit, Signal

_MAX_BULLETS = 3

# Only rule hits at or above this severity are "red flags" that the draft must
# surface. Lower-severity hints can ground the prompt but must not force an
# invented flag on an otherwise benign message.
_RED_FLAG_MIN_SEVERITY = 2

_BANNED_WORDS = {
    Language.ru: (
        "безопасно",
        "мошенничество",
        "мошенник",
        "аферист",
        "афёрист",
        "надежный",
        "надёжный",
        "законно",
    ),
    Language.uz_latn: ("xavfsiz", "firibgar", "firibgarlik", "ishonchli", "qonuniy"),
    Language.uz_cyrl: ("хавфсиз", "фирибгар", "фирибгарлик", "ишончли", "қонуний"),
}
_EN_BANNED = (
    "safe",
    "verified",
    "legitimate",
    "not a scam",
    "scammer",
    "fraudster",
    "fraud confirmed",
    "fraud",
)

_PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?\d[\d\s().-]{6,}\d)(?!\d)",
    re.IGNORECASE,
)
_ISO_DATE_RE = re.compile(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)")
_EMAIL_RE = re.compile(r"(?i)\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b")
_URL_OR_DOMAIN_RE = re.compile(
    r"(?ix)"
    r"\b(?:https?|hxxps?)://[^\s<>()]+"
    r"|\bwww\.[a-z0-9.-]+\.[a-z]{2,}(?:/[^\s<>()]*)?"
    r"|\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}\b"
    r"(?:/[^\s<>()]*)?"
)
_CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
_PASSPORT_RE = re.compile(r"(?i)(?<![a-z0-9])(?:[a-z]{2}\s?\d{7})(?![a-z0-9])")
_OTP_LABELED_RE = re.compile(
    r"(?iu)\b(?:otp|sms\s*code|sms\s*kod|kod|code|код|смс\s*код)[^\d]{0,20}\d{4,8}(?!\d)"
)
_PASSWORD_VALUE_RE = re.compile(r"(?iu)\b(?:password|parol|пароль)[\s:=\-]{0,10}\S{3,}")
_DIRECT_VERDICT_PATTERNS = (
    r"(?iu)\bмошенничеств\w*\b",
    r"(?i)\bfiribgarlik\w*\b",
    r"(?iu)\bфирибгарлик\w*\b",
)
_RISK_SCORE_PATTERNS = (
    r"(?i)\b(?:risk|danger|trust|safety)\s+(?:score|rating|probability)\b",
    r"(?iu)\b(?:уровень|оценка|вероятность)\s+(?:риска|опасности|доверия)\b",
    r"(?i)\b(?:xavf|ishonch)\s+(?:darajasi|bali|bahosi|ehtimoli)\b",
    r"(?iu)\b(?:хавф|ишонч)\s+(?:даражаси|бали|баҳоси|эҳтимоли)\b",
    r"(?i)\b(?:risk|danger|trust|safety|probability|chance)\b.{0,24}"
    r"\b\d{1,3}(?:[.,]\d+)?\s*(?:%|percent(?:age)?)",
    r"(?i)\b\d{1,3}(?:[.,]\d+)?\s*(?:%|percent(?:age)?)\b.{0,24}"
    r"\b(?:risk|danger|likely|probability|chance)\b",
    r"(?iu)\b(?:риск|опасност|довер|вероятност)\w*\b.{0,24}"
    r"\b\d{1,3}(?:[.,]\d+)?\s*(?:%|процент(?:а|ов)?)",
    r"(?i)\b(?:xavf|ishonch|ehtimol)\w*\b.{0,24}"
    r"\b\d{1,3}(?:[.,]\d+)?\s*(?:%|foiz)",
    r"(?iu)\b(?:хавф|ишонч|эҳтимол)\w*\b.{0,24}"
    r"\b\d{1,3}(?:[.,]\d+)?\s*(?:%|фоиз)",
)

_UNSAFE_PATTERNS = (
    r"(?i)\b(?:open|click|follow|visit)\s+(?:the\s+)?(?:link|url)\b",
    r"(?i)\bscan\s+(?:the\s+)?qr\b",
    r"(?i)\b(?:call|text|write|message)\s+(?:the\s+)?(?:number|phone)"
    r"\s+(?:from|in|inside)\s+(?:the\s+)?message\b",
    r"(?i)\breply\s+(?:to\s+)?(?:check|test)\b",
    r"(?iu)\b(?:откройте|открой|перейдите|перейди|нажмите|нажми)\s+"
    r"(?:по\s+)?(?:ссылк[ауе]|линк)\b",
    r"(?iu)\b(?:отсканируйте|сканируйте|сканируй)\s+(?:qr|qr-код|код)\b",
    r"(?iu)\b(?:позвоните|позвони|напишите|напиши)\s+"
    r"(?:на\s+)?(?:номер|телефон)\s+(?:из|в)\s+(?:сообщени[яие]|чата)\b",
    r"(?iu)\b(?:ответьте|ответь)\s+(?:чтобы\s+)?(?:проверить|протестировать)\b",
    r"(?i)\b(?:linkni|havolani)\s+(?:och|oching|bosing)\b",
    r"(?i)\bqr\s*(?:kodni|kodingizni)?\s*(?:skanerlang|skaner qil)\b",
    r"(?i)\b(?:xabardagi|chatdagi)\s+(?:raqam|telefon)(?:ga)?\s+"
    r"(?:qo'ng'iroq|qongiroq|yoz)\b",
    r"(?iu)\b(?:линкни|ҳаволани|хаволани)\s+(?:очинг|босинг)\b",
    r"(?iu)\bqr\s*(?:кодни)?\s*(?:сканерланг|сканер қилинг)\b",
    r"(?iu)\b(?:хабардаги|чатдаги)\s+(?:рақам|телефон)(?:га)?\s+"
    r"(?:қўнғироқ|ёз)\b",
)

_UNSUPPORTED_LOOKUP_PATTERNS = (
    r"(?i)\b(?:i|we|avvalo)\s+(?:checked|searched|verified)\s+(?:the\s+)?"
    r"(?:(?:external|public|internal)\s+)?"
    r"(?:database|records|account|identity|website|organization)\b",
    r"(?iu)\b(?:я|мы|avvalo)\s+проверил(?:а|и)?\s+"
    r"(?:базу|аккаунт|сч[её]т|личность|сайт|организацию)\b",
    r"(?i)\b(?:men|biz|avvalo)\s+(?:baza|hisob|shaxs|sayt|tashkilot)(?:ni)?\s+"
    r"tekshird(?:im|ik|i)\b",
    r"(?iu)\b(?:мен|биз|avvalo)\s+(?:база|ҳисоб|шахс|сайт|ташкилот)(?:ни)?\s+"
    r"текширд(?:им|ик|и)\b",
    r"(?i)\b(?:the\s+)?(?:(?:external|public|internal)\s+)?"
    r"(?:database|records)\s+(?:shows?|indicates?|confirms?|verified|found|returned|"
    r"contains?|has)\b",
    r"(?iu)\bпо\s+(?:(?:внешн|публичн|внутренн)\w*\s+)?базе(?:\s+данных)?\b"
    r".{0,80}\b(?:совпадени\w*\s+нет|ничего\s+не\s+найдено|подтвержд\w*|"
    r"показыва\w*|найден\w*)\b",
    r"(?iu)\b(?:(?:внешн|публичн|внутренн)\w*\s+)?база(?:\s+данных)?\s+"
    r"(?:показывает|подтверждает|не\s+нашла|нашла|содержит)\b",
    r"(?i)\b(?:(?:tashqi|ochiq|ichki)\s+)?baza(?:da|si)?\b.{0,80}\b"
    r"(?:tasdiq|ko['‘’]?rsat|topil|aniqla)\w*\b",
    r"(?iu)\b(?:(?:ташқи|очиқ|ички)\s+)?база(?:да|си)?\b.{0,80}\b"
    r"(?:тасдиқ|кўрсат|топил|аниқла)\w*\b",
)

_CASE_PROOF_PATTERNS = (
    r"(?i)\b(?:same|identical)\s+(?:reviewed\s+)?case\b.*\b(?:proves?|confirms?)\b",
    r"(?iu)\b(?:тот\s+же|такой\s+же)\s+случай\b.*\b(?:доказывает|подтверждает)\b",
    r"(?i)\b(?:aynan\s+o'sha|xuddi\s+shu)\s+(?:holat|voqea)\b.*\b(?:isbot|tasdiq)\b",
    r"(?iu)\b(?:айнан\s+ўша|худди\s+шу)\s+(?:ҳолат|воқеа)\b.*\b(?:исбот|тасдиқ)\b",
)

_INTERNAL_KNOWLEDGE_ID_RE = re.compile(r"(?i)\b(?:family|merchants)\.[a-z0-9_.-]+\b")
_BLOCKLIST_CLAIM_RE = re.compile(
    r"(?iu)\b(?:"
    r"blocklist|blacklist|ч[её]рн\w*\s+спис\w*|блоклист\w*|bloklist\w*|"
    r"qora\s+ro.yxat\w*|"
    r"(?:public\s+)?phishing\s+(?:list|feed|database)|"
    r"фишинг\w*\s+(?:спис\w*|баз\w*|лент\w*)|"
    r"(?:ochiq\s+)?fishing\s+(?:ro.yxat\w*|list|baza)|"
    r"фишинг\w*\s+(?:рўйхат\w*|база\w*)"
    r")\b"
)


class ValidationResult(BaseModel):
    """Result of deterministic draft validation."""

    ok: bool
    draft: DraftOutput
    reason: str | None = None
    no_signal: bool = False


def validate(
    draft: DraftOutput,
    signals: list[Signal],
    rule_hits: list[RuleHit],
    language: Language,
    *,
    knowledge_card_ids: list[str] | None = None,
    authoritative_lookup: bool = False,
) -> ValidationResult:
    """Validate and normalize one LLM draft."""

    _ = signals
    normalized = _truncate_blocks(draft)
    no_signal = len(rule_hits) == 0 and len(normalized.red_flags) == 0
    requires_red_flag = any(hit.severity >= _RED_FLAG_MIN_SEVERITY for hit in rule_hits)
    text = _joined_text(normalized)

    reason = _first_rejection_reason(
        text,
        normalized,
        requires_red_flag,
        language,
        knowledge_card_ids=knowledge_card_ids or [],
        authoritative_lookup=authoritative_lookup,
        rule_hits=rule_hits,
    )
    return ValidationResult(
        ok=reason is None,
        draft=normalized,
        reason=reason,
        no_signal=no_signal,
    )


def _truncate_blocks(draft: DraftOutput) -> DraftOutput:
    return draft.model_copy(
        update={
            "red_flags": list(draft.red_flags[:_MAX_BULLETS]),
            "verify": list(draft.verify[:_MAX_BULLETS]),
            "ask": list(draft.ask[:_MAX_BULLETS]),
        }
    )


def _joined_text(draft: DraftOutput) -> str:
    parts = [*draft.red_flags, draft.pattern or "", *draft.verify, *draft.ask]
    return "\n".join(part for part in parts if part).strip()


def _first_rejection_reason(
    text: str,
    draft: DraftOutput,
    requires_red_flag: bool,
    language: Language,
    *,
    knowledge_card_ids: list[str],
    authoritative_lookup: bool,
    rule_hits: list[RuleHit],
) -> str | None:
    lower = text.casefold()
    _ = language
    banned = (*_all_banned_words(), *_EN_BANNED)
    for word in banned:
        if re.search(rf"(?<![\w-]){re.escape(word.casefold())}(?![\w-])", lower):
            return f"banned verdict word: {word}"
    if any(re.search(pattern, text) for pattern in _DIRECT_VERDICT_PATTERNS):
        return "banned direct verdict"

    if any(re.search(pattern, text) for pattern in _RISK_SCORE_PATTERNS):
        return "risk score or probability leaked"

    if _EMAIL_RE.search(text) or _URL_OR_DOMAIN_RE.search(text):
        return "raw contact or URL leaked"
    has_blocklist_fact = any(
        hit.rule_id == "shared.link.blocklisted" for hit in rule_hits
    )
    # R6's sourced fact includes an ISO listed-since date. The broad phone
    # detector also matches YYYY-MM-DD, so remove only that exact shape and only
    # when the authoritative blocklist fact is present. All other digit runs
    # remain subject to the normal phone/account guards.
    phone_scan_text = _ISO_DATE_RE.sub("[DATE]", text) if has_blocklist_fact else text
    if _PHONE_RE.search(phone_scan_text):
        return "raw phone number leaked"
    if _CARD_RE.search(text):
        return "raw card/account number leaked"
    if _PASSPORT_RE.search(text):
        return "passport number leaked"
    if _OTP_LABELED_RE.search(text) or _PASSWORD_VALUE_RE.search(text):
        return "secret value leaked"
    for pattern in _UNSAFE_PATTERNS:
        if re.search(pattern, text):
            return "unsafe instruction to use suspicious contact path"
    if _INTERNAL_KNOWLEDGE_ID_RE.search(text) or any(
        card_id.casefold() in lower for card_id in knowledge_card_ids
    ):
        return "internal knowledge id leaked"
    for pattern in _CASE_PROOF_PATTERNS:
        if re.search(pattern, text):
            return "reviewed case represented as proof"
    # The legacy boolean cannot waive person/account/database prohibitions. R6's
    # only authoritative exception is the separately grounded URL blocklist fact.
    _ = authoritative_lookup
    for pattern in _UNSUPPORTED_LOOKUP_PATTERNS:
        if re.search(pattern, text):
            return "unsupported external lookup claim"
    if _BLOCKLIST_CLAIM_RE.search(text) and not has_blocklist_fact:
        return "unsupported URL blocklist claim"
    if not draft.verify:
        return "verify block is empty"
    if not draft.ask:
        return "ask block is empty"
    if requires_red_flag and not draft.red_flags:
        return "red_flags block is empty despite detected signals"
    known_rule_ids = {hit.rule_id for hit in rule_hits}
    declared_rule_ids = set(draft.addressed_rule_ids)
    invented_rule_ids = sorted(declared_rule_ids - known_rule_ids)
    if invented_rule_ids:
        return f"unknown addressed rule ids: {', '.join(invented_rule_ids)}"
    required_rule_ids = {
        hit.rule_id for hit in rule_hits if hit.severity >= _RED_FLAG_MIN_SEVERITY
    }
    missing_rule_ids = sorted(required_rule_ids - declared_rule_ids)
    if missing_rule_ids:
        return f"missing addressed rule ids: {', '.join(missing_rule_ids)}"
    return None


def _all_banned_words() -> tuple[str, ...]:
    return tuple(dict.fromkeys(word for words in _BANNED_WORDS.values() for word in words))
