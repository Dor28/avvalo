"""Deterministic safety validation for LLM drafts (§9).

``addressed_rule_ids`` is a language-independent floor for rule preservation:
it catches silently dropped authoritative facts, but a model declaring an ID is
not proof that its wording explained that fact well.
"""

from __future__ import annotations

import re
import unicodedata
from enum import StrEnum

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
}
# Uzbek is only ever answered in Latin script, but a model can still emit
# Cyrillic-Uzbek — often echoing Cyrillic input. These stay banned so a verdict
# cannot slip through in the script we no longer reply in.
_UZ_CYRL_BANNED = ("хавфсиз", "фирибгар", "фирибгарлик", "ишончли", "қонуний")
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
    r"(?i)\bno\s+(?:risk|danger|warning\s+signs?)\s+(?:was\s+|were\s+)?"
    r"(?:detected|found|identified)\b",
    r"(?i)\b(?:the\s+)?(?:company|organization|business)\s+"
    r"(?:is|appears|seems)\s+(?:trustworthy|reliable)\b",
    r"(?iu)\bриск\w*\s+не\s+(?:выявлен\w*|обнаружен\w*|найден\w*)\b",
    r"(?iu)\bкомпани\w*\s+можно\s+доверять\b",
    r"(?i)\bxavf\w*\s+(?:aniqlanmadi|topilmadi|ko['’]?rinmadi)\b",
    r"(?i)\b(?:bu\s+)?(?:kompaniya|tashkilot)(?:ga)?\s+"
    r"ishon(?:sa|ish)\w*\b",
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
    r"(?i)\b(?:i|we|avvalo)\s+(?:checked|searched|verified)\s+"
    r"(?:all|every)\s+(?:the\s+)?official\s+(?:databases?|records?)\b",
    r"(?iu)\b(?:я|мы|avvalo)\s+проверил(?:а|и)?\s+все\s+официальн\w*\s+"
    r"(?:баз\w*|реестр\w*)\b",
    r"(?i)\b(?:men|biz|avvalo)\s+barcha\s+rasmiy\s+"
    r"(?:baza|reyestr)(?:larni|ni)?\s+tekshird(?:im|ik|i)\b",
    r"(?i)\b(?:this\s+)?(?:phone\s+number|phone|number)\s+"
    r"(?:has\s+been\s+|was\s+)?reported\b",
    r"(?iu)\b(?:этот\s+)?(?:номер|телефон)\s+(?:был\s+)?(?:отмечен|зарегистрирован)\b",
    r"(?i)\b(?:bu\s+)?(?:telefon\s+)?raqam\s+(?:haqida\s+)?xabar\s+berilgan\b",
    r"(?i)\b(?:the\s+)?(?:company|organization|business)\s+"
    r"(?:does\s+not|doesn['’]?t)\s+exist\b",
    r"(?iu)\b(?:компани\w*|организаци\w*)\s+не\s+существует\b",
    r"(?i)\b(?:kompaniya|tashkilot)\s+mavjud\s+emas\b",
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


class ValidationReason(StrEnum):
    """Fixed safety-rejection codes safe to reuse in retries and metadata logs."""

    DRAFT_FAILED = "draft failed deterministic safety validation"
    BANNED_VERDICT_WORD = "banned verdict word"
    BANNED_DIRECT_VERDICT = "banned direct verdict"
    RISK_SCORE = "risk score or probability leaked"
    RAW_CONTACT_OR_URL = "raw contact or URL leaked"
    RAW_PHONE = "raw phone number leaked"
    RAW_CARD = "raw card/account number leaked"
    PASSPORT = "passport number leaked"
    SECRET = "secret value leaked"
    UNSAFE_CONTACT_PATH = "unsafe instruction to use suspicious contact path"
    INTERNAL_KNOWLEDGE_ID = "internal knowledge id leaked"
    REVIEWED_CASE_AS_PROOF = "reviewed case represented as proof"
    UNSUPPORTED_EXTERNAL_LOOKUP = "unsupported external lookup claim"
    UNSUPPORTED_BLOCKLIST_CLAIM = "unsupported URL blocklist claim"
    WRONG_LANGUAGE_SCRIPT = "wrong language script"
    VERIFY_BLOCK_EMPTY = "verify block is empty"
    ASK_BLOCK_EMPTY = "ask block is empty"
    REQUIRED_RED_FLAGS_EMPTY = "red_flags block is empty despite detected signals"
    UNKNOWN_RULE_IDS = "unknown addressed rule ids"
    MISSING_RULE_IDS = "missing addressed rule ids"


class ValidationResult(BaseModel):
    """Result of deterministic draft validation."""

    ok: bool
    draft: DraftOutput
    reason: ValidationReason | None = None
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
) -> ValidationReason | None:
    scan_text = _normalize_for_matching(text)
    lower = scan_text.casefold()
    banned = (*_all_banned_words(), *_EN_BANNED)
    for word in banned:
        if re.search(rf"(?<![\w-]){re.escape(word.casefold())}(?![\w-])", lower):
            return ValidationReason.BANNED_VERDICT_WORD
    if any(re.search(pattern, scan_text) for pattern in _DIRECT_VERDICT_PATTERNS):
        return ValidationReason.BANNED_DIRECT_VERDICT

    if any(re.search(pattern, scan_text) for pattern in _RISK_SCORE_PATTERNS):
        return ValidationReason.RISK_SCORE

    if _EMAIL_RE.search(scan_text) or _URL_OR_DOMAIN_RE.search(scan_text):
        return ValidationReason.RAW_CONTACT_OR_URL
    has_blocklist_fact = any(
        hit.rule_id == "shared.link.blocklisted" for hit in rule_hits
    )
    # R6's sourced fact includes an ISO listed-since date. The broad phone
    # detector also matches YYYY-MM-DD, so remove only that exact shape and only
    # when the authoritative blocklist fact is present. All other digit runs
    # remain subject to the normal phone/account guards.
    phone_scan_text = (
        _ISO_DATE_RE.sub("[DATE]", scan_text) if has_blocklist_fact else scan_text
    )
    if _PHONE_RE.search(phone_scan_text):
        return ValidationReason.RAW_PHONE
    if _CARD_RE.search(scan_text):
        return ValidationReason.RAW_CARD
    if _PASSPORT_RE.search(scan_text):
        return ValidationReason.PASSPORT
    if _OTP_LABELED_RE.search(scan_text) or _PASSWORD_VALUE_RE.search(scan_text):
        return ValidationReason.SECRET
    for pattern in _UNSAFE_PATTERNS:
        if re.search(pattern, scan_text):
            return ValidationReason.UNSAFE_CONTACT_PATH
    if _INTERNAL_KNOWLEDGE_ID_RE.search(scan_text) or any(
        card_id.casefold() in lower for card_id in knowledge_card_ids
    ):
        return ValidationReason.INTERNAL_KNOWLEDGE_ID
    for pattern in _CASE_PROOF_PATTERNS:
        if re.search(pattern, scan_text):
            return ValidationReason.REVIEWED_CASE_AS_PROOF
    # The legacy boolean cannot waive person/account/database prohibitions. R6's
    # only authoritative exception is the separately grounded URL blocklist fact.
    _ = authoritative_lookup
    for pattern in _UNSUPPORTED_LOOKUP_PATTERNS:
        if re.search(pattern, scan_text):
            return ValidationReason.UNSUPPORTED_EXTERNAL_LOOKUP
    if _BLOCKLIST_CLAIM_RE.search(scan_text) and not has_blocklist_fact:
        return ValidationReason.UNSUPPORTED_BLOCKLIST_CLAIM
    if _uses_wrong_script(scan_text, language):
        return ValidationReason.WRONG_LANGUAGE_SCRIPT
    if not draft.verify:
        return ValidationReason.VERIFY_BLOCK_EMPTY
    if not draft.ask:
        return ValidationReason.ASK_BLOCK_EMPTY
    if requires_red_flag and not draft.red_flags:
        return ValidationReason.REQUIRED_RED_FLAGS_EMPTY
    known_rule_ids = {hit.rule_id for hit in rule_hits}
    declared_rule_ids = set(draft.addressed_rule_ids)
    if declared_rule_ids - known_rule_ids:
        return ValidationReason.UNKNOWN_RULE_IDS
    required_rule_ids = {
        hit.rule_id for hit in rule_hits if hit.severity >= _RED_FLAG_MIN_SEVERITY
    }
    if required_rule_ids - declared_rule_ids:
        return ValidationReason.MISSING_RULE_IDS
    return None


def _normalize_for_matching(text: str) -> str:
    """Collapse common output obfuscation without changing the visible draft."""

    normalized = unicodedata.normalize("NFKC", text)
    without_format_controls = "".join(
        character for character in normalized if unicodedata.category(character) != "Cf"
    )
    return re.sub(r"[*~`]+", "", without_format_controls)


def _uses_wrong_script(text: str, language: Language) -> bool:
    """Enforce the product rule that Uzbek replies use Latin script only."""

    cyrillic_count = len(re.findall(r"[\u0400-\u052f]", text))
    return language is Language.uz_latn and cyrillic_count > 0


def _all_banned_words() -> tuple[str, ...]:
    words = (*(w for words in _BANNED_WORDS.values() for w in words), *_UZ_CYRL_BANNED)
    return tuple(dict.fromkeys(words))
