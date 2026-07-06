"""Final user-facing message formatting."""

from functools import cache

from app.engine.rules import load_rule_pack
from app.engine.types import CheckStatus, DraftOutput, Language

BOT_LINK = "https://t.me/Avvalo_official_bot"

_FAMILY_LABELS = {
    "credential_theft": {
        Language.uz_latn: "kod yoki maxfiy ma'lumot so'rash",
        Language.uz_cyrl: "код ёки махфий маълумот сўраш",
        Language.ru: "запрос кодов или секретных данных",
    },
    "urgency_secrecy": {
        Language.uz_latn: "shoshirish yoki sir tutishni so'rash",
        Language.uz_cyrl: "шошириш ёки сир тутишни сўраш",
        Language.ru: "срочность или просьба держать в тайне",
    },
    "authority_impersonation": {
        Language.uz_latn: "rasmiy tashkilot yoki yaqin odam nomidan yozish",
        Language.uz_cyrl: "расмий ташкилот ёки яқин одам номидан ёзиш",
        Language.ru: "сообщение от имени организации или близкого",
    },
    "upfront_payment": {
        Language.uz_latn: "oldindan to'lov yoki depozit so'rash",
        Language.uz_cyrl: "олдиндан тўлов ёки депозит сўраш",
        Language.ru: "предоплата или депозит до проверки",
    },
    "verification_avoidance": {
        Language.uz_latn: "mustaqil tekshiruvdan qochish",
        Language.uz_cyrl: "мустақил текширувдан қочиш",
        Language.ru: "уход от независимой проверки",
    },
    "implausible_promise": {
        Language.uz_latn: "juda yaxshi ko'rinadigan va'da",
        Language.uz_cyrl: "жуда яхши кўринадиган ваъда",
        Language.ru: "слишком выгодное обещание",
    },
    "suspicious_link_qr": {
        Language.uz_latn: "havola yoki QR orqali bosim",
        Language.uz_cyrl: "ҳавола ёки QR орқали босим",
        Language.ru: "давление через ссылку или QR",
    },
    "receipt_inconsistency": {
        Language.uz_latn: "to'lov hikoyasidagi nomuvofiqlik",
        Language.uz_cyrl: "тўлов ҳикоясидаги номувофиқлик",
        Language.ru: "несостыковка в истории оплаты",
    },
    "amount_mismatch": {
        Language.uz_latn: "summa yoki qaytarim talabi mos kelmasligi",
        Language.uz_cyrl: "сумма ёки қайтарим талаби мос келмаслиги",
        Language.ru: "несовпадение суммы или просьба о возврате",
    },
    "edited_screenshot_hint": {
        Language.uz_latn: "skrinshotni to'lov isboti sifatida ko'rsatish",
        Language.uz_cyrl: "скриншотни тўлов исботи сифатида кўрсатиш",
        Language.ru: "скриншот как доказательство оплаты",
    },
    "fake_courier_refund": {
        Language.uz_latn: "pul tasdiqlanmasdan jo'natishga bosim",
        Language.uz_cyrl: "пул тасдиқланмасдан жўнатишга босим",
        Language.ru: "давление отправить товар до подтверждения",
    },
    "verify_in_bank_app": {
        Language.uz_latn: "bank ilovasida tasdiqlash zarurati",
        Language.uz_cyrl: "банк иловасида тасдиқлаш зарурати",
        Language.ru: "нужно проверить в банковском приложении",
    },
}

_SHARE_COPY = {
    Language.uz_latn: {
        "lead": "Men Avvalo bilan shubhali xabarni tekshirdim.",
        "families": "Topilgan belgilar: {families}.",
        "generic": "Men Avvalo bilan shubhali xabarni tekshirdim.",
        "caution": "Javob berish yoki to'lov qilishdan oldin mustaqil tekshiring.",
        "cta": f"O'zingiznikini tekshiring: {BOT_LINK}",
    },
    Language.uz_cyrl: {
        "lead": "Мен Avvalo билан шубҳали хабарни текширдим.",
        "families": "Топилган белгилар: {families}.",
        "generic": "Мен Avvalo билан шубҳали хабарни текширдим.",
        "caution": "Жавоб бериш ёки тўлов қилишдан олдин мустақил текширинг.",
        "cta": f"Ўзингизникини текширинг: {BOT_LINK}",
    },
    Language.ru: {
        "lead": "Я проверил(а) подозрительное сообщение в Avvalo.",
        "families": "Найденные признаки: {families}.",
        "generic": "Я проверил(а) подозрительное сообщение в Avvalo.",
        "caution": "Не отвечайте и не платите до независимой проверки.",
        "cta": f"Проверьте свое: {BOT_LINK}",
    },
}

_HEADINGS = {
    Language.uz_latn: {
        "red_flags": "🚩 **Xavf belgilari**",
        "pattern": "**Bosim usuli:**",
        "verify": "✅ **Nimani tekshirish kerak**",
        "ask": "❓ **Nimani so'rash kerak**",
        "no_signal": (
            "Aniq xavf belgilari topilmadi. Bu holatda xavf yo'qligini isbotlamaydi."
        ),
        "limitation": (
            "ℹ️ Avvalo yuborilgan vaziyatdagi belgilarni tahlil qildi; "
            "u shaxsni tekshirmadi va yakuniy kafolat bermaydi."
        ),
        "fallback": (
            "Avvalo bu javobni tekshiruvdan o'tkaza olmadi. Kodlarni ulashmang "
            "va to'lov qilmang; avval rasmiy ilova yoki mustaqil topgan aloqa "
            "kanali orqali tekshiring."
        ),
    },
    Language.uz_cyrl: {
        "red_flags": "🚩 **Хавф белгилари**",
        "pattern": "**Босим усули:**",
        "verify": "✅ **Нимани текшириш керак**",
        "ask": "❓ **Нимани сўраш керак**",
        "no_signal": (
            "Аниқ хавф белгилари топилмади. Бу ҳолатда хавф йўқлигини исботламайди."
        ),
        "limitation": (
            "ℹ️ Avvalo юборилган вазиятдаги белгиларни таҳлил қилди; "
            "у шахсни текширмади ва якуний кафолат бермайди."
        ),
        "fallback": (
            "Avvalo бу жавобни текширувдан ўтказа олмади. Кодларни улашманг "
            "ва тўлов қилманг; аввал расмий илова ёки мустақил топган алоқа "
            "канали орқали текширинг."
        ),
    },
    Language.ru: {
        "red_flags": "🚩 **Тревожные признаки**",
        "pattern": "**Схема давления:**",
        "verify": "✅ **Что проверить**",
        "ask": "❓ **Что спросить**",
        "no_signal": (
            "Явных тревожных признаков в присланном содержании не найдено. "
            "Это не доказывает отсутствие риска."
        ),
        "limitation": (
            "ℹ️ Avvalo анализирует признаки в ситуации, а не личность отправителя, "
            "и не даёт окончательных гарантий."
        ),
        "fallback": (
            "Avvalo не смог подготовить ответ, который проходит проверку безопасности. "
            "Не сообщайте коды и не платите, пока не проверите ситуацию через официальное "
            "приложение или контакт, найденный самостоятельно."
        ),
    },
}


def share_summary(rule_ids: list[str], language: Language | str, face: str) -> str:
    """Build a deterministic, content-free share warning from stored rule IDs."""

    resolved_language = _coerce_language(language)
    labels = _top_family_labels(rule_ids, resolved_language, face)
    copy = _SHARE_COPY[resolved_language]
    if not labels:
        return "\n".join([copy["generic"], copy["cta"]])

    return "\n".join(
        [
            copy["lead"],
            copy["families"].format(families=", ".join(labels)),
            copy["caution"],
            copy["cta"],
        ]
    )

_STATUS_MESSAGES = {
    CheckStatus.rate_limited: {
        Language.uz_latn: "Bugungi tekshiruv limiti tugadi. Iltimos, ertaga qayta urinib ko'ring.",
        Language.uz_cyrl: "Бугунги текширув лимити тугади. Илтимос, эртага қайта уриниб кўринг.",
        Language.ru: "Дневной лимит проверок исчерпан. Пожалуйста, попробуйте завтра.",
    },
    CheckStatus.empty_input: {
        Language.uz_latn: "Tekshirish uchun matn yuboring.",
        Language.uz_cyrl: "Текшириш учун матн юборинг.",
        Language.ru: "Пришлите текст для проверки.",
    },
    CheckStatus.low_ocr: {
        Language.uz_latn: "Rasmni aniq o'qiy olmadik. Iltimos, muhim matnni yozib yuboring.",
        Language.uz_cyrl: "Расмни аниқ ўқий олмадик. Илтимос, муҳим матнни ёзиб юборинг.",
        Language.ru: (
            "Не удалось чётко прочитать изображение. "
            "Пожалуйста, пришлите важный текст сообщением."
        ),
    },
    CheckStatus.timeout: {
        Language.uz_latn: "Tekshiruv o'z vaqtida yakunlanmadi. Iltimos, qayta urinib ko'ring.",
        Language.uz_cyrl: "Текширув ўз вақтида якунланмади. Илтимос, қайта уриниб кўринг.",
        Language.ru: "Проверка не успела завершиться. Пожалуйста, попробуйте ещё раз.",
    },
    CheckStatus.llm_error: {
        Language.uz_latn: "Hozir bu xabarni tahlil qila olmadik. Iltimos, qayta urinib ko'ring.",
        Language.uz_cyrl: "Ҳозир бу хабарни таҳлил қила олмадик. Илтимос, қайта уриниб кўринг.",
        Language.ru: (
            "Сейчас не удалось проанализировать это сообщение. "
            "Пожалуйста, попробуйте ещё раз."
        ),
    },
    CheckStatus.unsupported_media: {
        Language.uz_latn: "Iltimos, o'qilishi mumkin bo'lgan rasm yoki matn yuboring.",
        Language.uz_cyrl: "Илтимос, ўқилиши мумкин бўлган расм ёки матн юборинг.",
        Language.ru: "Пожалуйста, пришлите читаемое изображение или текст.",
    },
}


def format_result(draft: DraftOutput, language: Language, *, no_signal: bool = False) -> str:
    """Format a validated draft into the visible Avvalo response block."""

    copy = draft.model_copy(
        update={
            "red_flags": draft.red_flags[:3],
            "verify": draft.verify[:3],
            "ask": draft.ask[:3],
        }
    )
    labels = _HEADINGS[language]
    blocks: list[str] = []

    if no_signal:
        blocks.append(labels["no_signal"])
    elif copy.red_flags:
        blocks.append(_section(labels["red_flags"], copy.red_flags))

    if copy.pattern:
        blocks.append(f"{labels['pattern']} {copy.pattern}")
    if copy.verify:
        blocks.append(_section(labels["verify"], copy.verify))
    if copy.ask:
        blocks.append(_section(labels["ask"], copy.ask))
    blocks.append(labels["limitation"])
    return "\n\n".join(blocks)


def format_fallback(language: Language) -> str:
    """Return the localized safety fallback message."""

    return _HEADINGS[language]["fallback"]


def format_status_message(status: CheckStatus, language: Language) -> str:
    """Return the localized user-facing message for a non-success status."""

    return _STATUS_MESSAGES.get(status, _STATUS_MESSAGES[CheckStatus.unsupported_media])[
        language
    ]


def format_output(draft: DraftOutput, language: Language, *, no_signal: bool = False) -> str:
    """Alias for callers/tests that use the older name."""

    return format_result(draft, language, no_signal=no_signal)


def build_message(draft: DraftOutput, language: Language, *, no_signal: bool = False) -> str:
    """Alias for callers/tests that use the channel-facing name."""

    return format_result(draft, language, no_signal=no_signal)


def format_check(draft: DraftOutput, language: Language, *, no_signal: bool = False) -> str:
    """Alias for callers/tests that use the check-facing name."""

    return format_result(draft, language, no_signal=no_signal)


def _section(title: str, bullets: list[str]) -> str:
    rendered = "\n".join(f"- {bullet}" for bullet in bullets)
    return f"{title}\n{rendered}"


def _coerce_language(language: Language | str) -> Language:
    try:
        return language if isinstance(language, Language) else Language(language)
    except ValueError:
        return Language.uz_latn


def _top_family_labels(rule_ids: list[str], language: Language, face: str) -> list[str]:
    by_rule = _rules_by_id(face)
    ranked: dict[str, tuple[int, int]] = {}
    for index, rule_id in enumerate(rule_ids):
        rule = by_rule.get(rule_id)
        if rule is None:
            continue
        current = ranked.get(rule.family)
        if current is None or rule.severity > current[0]:
            ranked[rule.family] = (rule.severity, index)

    families = sorted(ranked, key=lambda family: (-ranked[family][0], ranked[family][1], family))
    return [_family_label(family, language) for family in families[:3]]


@cache
def _rules_by_id(face: str):
    try:
        pack = load_rule_pack(face)
    except (FileNotFoundError, ValueError):
        return {}
    return {rule.id: rule for rule in pack.rules}


def _family_label(family: str, language: Language) -> str:
    localized = _FAMILY_LABELS.get(family, {})
    return localized.get(language) or family.replace("_", " ")
