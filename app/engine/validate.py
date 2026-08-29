"""Deterministic safety validation for LLM drafts (§9).

``addressed_rule_ids`` is a language-independent floor for rule preservation:
it catches silently dropped authoritative facts, but a model declaring an ID is
not proof that its wording explained that fact well.

Two per-bullet filters run before the draft-level scan (PIPELINE_V2 §3, §5):
grounding drops a red flag that cannot name the detected fact it rests on, and
the filler blocklist drops a bullet that is nothing but a stock safety phrase.
Both remove the offending bullet instead of rejecting the whole draft, because a
rejection costs a corrective retry and often lands on ``safety_fallback`` —
replacing a partly-good answer with fixed copy.
"""

from __future__ import annotations

import re
import unicodedata
from enum import StrEnum

from pydantic import BaseModel

from app.engine.types import DraftOutput, Evidence, Language, RuleHit, Signal

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

# ``prompts/check.txt`` ("INCOMING PAYMENT CLAIMS") tells the model never to state
# that an incoming payment arrived on the strength of a screenshot or receipt.
# These patterns are the deterministic counterpart: the prompt asks, the validator
# enforces. An apostrophe class covers the Uzbek straight, curly, and modifier
# quote variants used interchangeably for o' and g'.
_PAYMENT_CONFIRMED_PATTERNS = (
    r"(?iu)\b(?:деньги|средства)\s+(?:пришли|поступили|получены)\b",
    r"(?iu)\b(?:оплата|платёж|платеж|перевод)\s+(?:прошла|прошёл|прошел|"
    r"получен(?:а)?|поступил(?:а)?|подтвержд[её]н(?:а)?)\b",
    r"(?iu)\b(?:платёж|платеж|перевод|чек|квитанция)\s+(?:настоящий|настоящая|"
    r"подлинный|подлинная)\b",
    # Uzbek negates morphologically (keldi → kelmadi, o'tdi → o'tmadi), so the
    # affirmative form is already distinct from its own negation.
    r"(?i)\bpul\s+(?:keldi|tushdi|o['‘’ʻ]?tdi)\b",
    r"(?i)\bto['‘’ʻ]?lov\s+(?:o['‘’ʻ]?tdi|keldi|tushdi|tasdiqlandi)\b",
    r"(?iu)\bпул\s+(?:келди|тушди)\b",
    r"(?iu)\bтўлов\s+(?:ўтди|келди|тушди|тасдиқланди)\b",
)
# The desired guidance discusses the claim in order to reject it ("a screenshot is
# not proof that the money arrived"). Russian keeps the claim phrase intact under
# negation, so an affirmative claim is distinguished from a disclaimed one by an
# explicit proof/confirmation construction in the same sentence. A bare negation is
# deliberately not enough: "не волнуйтесь, деньги пришли" stays a claim.
_PAYMENT_DISCLAIMER_RE = re.compile(
    r"(?iu)(?:"
    r"не\s+(?:доказыва|подтвержда|означа|значит|гарантиру|явля)\w*|"
    r"не\s+доказательств\w*|"
    r"(?:пока|ещ[её])\s+не\b|"
    r"не\s+факт\b|"
    r"isbot\s*(?:emas|lamaydi)|tasdiqla(?:maydi|nmagan)|degani\s+emas|"
    r"hali\s+emas|"
    r"исбот\s*(?:эмас|ламайди)|тасдиқла(?:майди|нмаган)|дегани\s+эмас"
    r")"
)
_SENTENCE_SPLIT_RE = re.compile(r"[.!?\n;]+")

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


# Whole-bullet stock phrases. ``prompts/check.txt`` already asks the model to
# avoid them; these are the deterministic counterpart. Matched with `fullmatch`
# against the bullet stripped of edge punctuation, so a bullet that carries a
# concrete instruction *and* a stock phrase survives — the goal is removing
# content-free bullets, not policing style.
_FILLER_PATTERNS = (
    # Russian
    r"(?:пожалуйста,?\s*)?будьте\s+(?:осторожны|бдительны|внимательны)"
    r"(?:\s+в\s+интернете)?",
    r"(?:пожалуйста,?\s*)?соблюдайте\s+осторожность(?:\s+в\s+интернете)?",
    r"проявляйте\s+(?:бдительность|осторожность|внимательность)",
    r"всегда\s+проверяйте\s+(?:информацию|источники|официальные\s+источники)",
    r"не\s+доверяйте\s+(?:незнакомцам|незнакомым\s+людям)",
    r"это\s+может\s+быть\s+(?:опасно|небезопасно)",
    # Uzbek, Latin script (apostrophes are normalized before matching)
    r"(?:iltimos,?\s*)?(?:ehtiyot|hushyor|diqqatli)\s+bo'ling"
    r"(?:\s+internetda)?",
    r"doimo\s+(?:rasmiy\s+)?(?:manbalarni|ma'lumotlarni)\s+tekshiring",
    r"notanish\s+(?:odamlarga|kishilarga)\s+ishonmang",
    r"bu\s+xavfli\s+bo'lishi\s+mumkin",
    # Uzbek, Cyrillic script — banned in replies, but a bullet can still arrive
    # in it and must not survive the filter merely by changing script.
    r"(?:илтимос,?\s*)?(?:эҳтиёт|ҳушёр|диққатли)\s+бўлинг",
    r"доимо\s+(?:расмий\s+)?манбаларни\s+текширинг",
    # English, for a model that slips out of the target language
    r"(?:please\s+)?be\s+(?:careful|vigilant|cautious)(?:\s+online)?",
    r"exercise\s+caution(?:\s+online)?",
    r"stay\s+safe(?:\s+online)?",
    r"always\s+verify\s+(?:information|sources|official\s+sources)",
)

_FILLER_RE = tuple(re.compile(pattern) for pattern in _FILLER_PATTERNS)
# The same straight/curly/modifier quote variants the rule matcher folds, so the
# Uzbek o' and g' spellings are one phrase here however the apostrophe is typed.
_UZ_APOSTROPHES = str.maketrans(
    {"’": "'", "‘": "'", "`": "'", "ʼ": "'", "՚": "'", "´": "'"}
)
_BULLET_EDGE_RE = re.compile(r"^[\s\W_]+|[\s\W_]+$")


class ValidationReason(StrEnum):
    """Fixed safety-rejection codes safe to reuse in retries and metadata logs."""

    DRAFT_FAILED = "draft failed deterministic safety validation"
    UNGROUNDED_RED_FLAG = "red flag does not name a detected fact"
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
    PAYMENT_CONFIRMED_CLAIM = "incoming payment represented as confirmed"
    WRONG_LANGUAGE_SCRIPT = "wrong language script"
    VERIFY_BLOCK_EMPTY = "verify block is empty"
    ASK_BLOCK_EMPTY = "ask block is empty"
    REQUIRED_RED_FLAGS_EMPTY = "red_flags block is empty despite detected signals"
    UNKNOWN_RULE_IDS = "unknown addressed rule ids"
    MISSING_RULE_IDS = "missing addressed rule ids"


class ValidationResult(BaseModel):
    """Result of deterministic draft validation.

    The two counters carry no bullet text — only how many bullets each filter
    removed — so observability can watch the rates without recording model
    output.
    """

    ok: bool
    draft: DraftOutput
    reason: ValidationReason | None = None
    no_signal: bool = False
    dropped_ungrounded: int = 0
    dropped_filler: int = 0
    grounding_unsupported: bool = False


def validate(
    draft: DraftOutput,
    signals: list[Signal],
    rule_hits: list[RuleHit],
    language: Language,
    *,
    knowledge_card_ids: list[str] | None = None,
    require_grounding: bool = False,
) -> ValidationResult:
    """Validate and normalize one LLM draft.

    Per-bullet filters run before truncation so the best three bullets survive
    rather than the first three of a list that still contains rejects.
    """

    # ``model_copy(update=...)`` bypasses field validation, so a caller can hand
    # this boundary a list of bare strings. Normalizing here keeps the validator
    # total: an unhandled AttributeError would escape ``run_check`` instead of
    # degrading to ``safety_fallback``, which is the wrong failure mode for the
    # component whose whole job is to fail safe.
    filtered = draft.model_copy(update={"red_flags": _as_evidence(draft.red_flags)})
    dropped_ungrounded = 0
    grounding_unsupported = False
    if require_grounding:
        kept, dropped_ungrounded, grounding_unsupported = _partition_red_flags(
            filtered.red_flags,
            rule_hits=rule_hits,
            signals=signals,
            knowledge_card_ids=knowledge_card_ids or [],
        )
        filtered = filtered.model_copy(update={"red_flags": kept})

    filtered, dropped_filler = _drop_filler(filtered)
    normalized = _truncate_blocks(filtered)
    no_signal = len(rule_hits) == 0 and len(normalized.red_flags) == 0
    requires_red_flag = any(hit.severity >= _RED_FLAG_MIN_SEVERITY for hit in rule_hits)
    text = _joined_text(normalized)

    reason = _first_rejection_reason(
        text,
        normalized,
        requires_red_flag,
        language,
        knowledge_card_ids=knowledge_card_ids or [],
        rule_hits=rule_hits,
    )
    if reason is ValidationReason.REQUIRED_RED_FLAGS_EMPTY and dropped_ungrounded:
        # The block is empty *because* grounding removed every bullet. Reporting
        # the precise cause is what routes the retry to the grounding contract
        # instead of the generic don't-leak-contacts reminder.
        reason = ValidationReason.UNGROUNDED_RED_FLAG
    return ValidationResult(
        ok=reason is None,
        draft=normalized,
        reason=reason,
        no_signal=no_signal,
        dropped_ungrounded=dropped_ungrounded,
        dropped_filler=dropped_filler,
        grounding_unsupported=grounding_unsupported,
    )


def _as_evidence(red_flags: list[Evidence]) -> list[Evidence]:
    """Coerce any bare string that bypassed field validation into ``Evidence``."""

    return [
        item if isinstance(item, Evidence) else Evidence(text=str(item))
        for item in red_flags
    ]


def _partition_red_flags(
    red_flags: list[Evidence],
    *,
    rule_hits: list[RuleHit],
    signals: list[Signal],
    knowledge_card_ids: list[str],
) -> tuple[list[Evidence], int, bool]:
    """Keep only red flags naming a fact this check actually detected.

    Returns the surviving bullets, how many were dropped, and whether the
    compatibility floor applied.

    A model that cites an id outside the evidence set has hallucinated its
    grounding, and the bullet goes. A model that emits no ``source_id`` at all
    has not implemented the field — a different failure, and one that would
    otherwise empty every red-flag block against a provider whose JSON-schema
    support does not extend to nested objects. In that single case the bullets
    are kept and the caller records ``grounding_unsupported`` so the gap is
    visible in observability rather than silently degrading answers. Enforcement
    becomes strict as soon as the model demonstrates it understands the field.
    """

    if not red_flags:
        return [], 0, False

    evidence_ids = (
        {hit.rule_id for hit in rule_hits}
        | {signal.kind for signal in signals}
        | set(knowledge_card_ids)
    )
    grounded = [flag for flag in red_flags if flag.source_id in evidence_ids]
    cited = [flag for flag in red_flags if flag.source_id]
    if not cited:
        return list(red_flags), 0, True
    return grounded, len(red_flags) - len(grounded), False


def _drop_filler(draft: DraftOutput) -> tuple[DraftOutput, int]:
    """Remove bullets that are nothing but a stock safety phrase.

    A ``verify``/``ask`` bullet is kept when it is the last one standing: vague
    advice beats an empty block, which would fail the draft outright and return
    fixed fallback copy instead.
    """

    kept_flags = [flag for flag in draft.red_flags if not _is_filler(flag.text)]
    kept_verify = _filtered_or_last(draft.verify)
    kept_ask = _filtered_or_last(draft.ask)
    dropped = (
        len(draft.red_flags)
        - len(kept_flags)
        + len(draft.verify)
        - len(kept_verify)
        + len(draft.ask)
        - len(kept_ask)
    )
    if not dropped:
        return draft, 0
    return (
        draft.model_copy(
            update={"red_flags": kept_flags, "verify": kept_verify, "ask": kept_ask}
        ),
        dropped,
    )


def _filtered_or_last(bullets: list[str]) -> list[str]:
    kept = [bullet for bullet in bullets if not _is_filler(bullet)]
    if kept or not bullets:
        return kept
    return [bullets[0]]


def _is_filler(bullet: str) -> bool:
    stripped = _BULLET_EDGE_RE.sub(
        "", unicodedata.normalize("NFKC", bullet).translate(_UZ_APOSTROPHES).casefold()
    )
    collapsed = re.sub(r"\s+", " ", stripped)
    return any(pattern.fullmatch(collapsed) for pattern in _FILLER_RE)


def _truncate_blocks(draft: DraftOutput) -> DraftOutput:
    return draft.model_copy(
        update={
            "red_flags": list(draft.red_flags[:_MAX_BULLETS]),
            "verify": list(draft.verify[:_MAX_BULLETS]),
            "ask": list(draft.ask[:_MAX_BULLETS]),
        }
    )


def _joined_text(draft: DraftOutput) -> str:
    parts = [
        *(flag.text for flag in draft.red_flags),
        draft.pattern or "",
        *draft.verify,
        *draft.ask,
    ]
    return "\n".join(part for part in parts if part).strip()


def _first_rejection_reason(
    text: str,
    draft: DraftOutput,
    requires_red_flag: bool,
    language: Language,
    *,
    knowledge_card_ids: list[str],
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
    if _PHONE_RE.search(scan_text):
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
    if _claims_payment_confirmed(scan_text):
        return ValidationReason.PAYMENT_CONFIRMED_CLAIM
    for pattern in _CASE_PROOF_PATTERNS:
        if re.search(pattern, scan_text):
            return ValidationReason.REVIEWED_CASE_AS_PROOF
    for pattern in _UNSUPPORTED_LOOKUP_PATTERNS:
        if re.search(pattern, scan_text):
            return ValidationReason.UNSUPPORTED_EXTERNAL_LOOKUP
    # There is no URL blocklist behind the product any more, so a model claiming
    # a domain is listed is always claiming an external check we did not make.
    if _BLOCKLIST_CLAIM_RE.search(scan_text):
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


def _claims_payment_confirmed(text: str) -> bool:
    """Report whether any sentence asserts an incoming payment as confirmed.

    Scoping to a sentence keeps the disclaimer attached to the claim it rejects,
    so "a screenshot does not prove the money arrived" passes while a bare
    "the money arrived" in the next bullet still fails.
    """

    for sentence in _SENTENCE_SPLIT_RE.split(text):
        if not any(re.search(pattern, sentence) for pattern in _PAYMENT_CONFIRMED_PATTERNS):
            continue
        if not _PAYMENT_DISCLAIMER_RE.search(sentence):
            return True
    return False


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
