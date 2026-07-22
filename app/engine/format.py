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
        "lead": "Men Avvalo bilan shubhali vaziyatni ko'rib chiqdim.",
        "families": "Topilgan belgilar: {families}.",
        "generic": "Men Avvalo bilan shubhali vaziyatni ko'rib chiqdim.",
        "caution": "Harakat qilishdan oldin muhim ma'lumotlarni mustaqil tekshiring.",
        "cta": f"Shubhangiz bormi? Avvalo'ga yuboring: {BOT_LINK}",
    },
    Language.uz_cyrl: {
        "lead": "Мен Avvalo билан шубҳали вазиятни кўриб чиқдим.",
        "families": "Топилган белгилар: {families}.",
        "generic": "Мен Avvalo билан шубҳали вазиятни кўриб чиқдим.",
        "caution": "Ҳаракат қилишдан олдин муҳим маълумотларни мустақил текширинг.",
        "cta": f"Шубҳангиз борми? Avvalo'га юборинг: {BOT_LINK}",
    },
    Language.ru: {
        "lead": "Я разобрал(а) сомнительную ситуацию с Avvalo.",
        "families": "Найденные признаки: {families}.",
        "generic": "Я разобрал(а) сомнительную ситуацию с Avvalo.",
        "caution": "Проверьте важные сведения самостоятельно до того, как действовать.",
        "cta": f"Есть сомнения? Отправьте ситуацию в Avvalo: {BOT_LINK}",
    },
}

_HEADINGS = {
    Language.uz_latn: {
        "red_flags": "🚩 **Xavf belgilari**",
        "pattern": "**Qanday bosim ishlatyapti:**",
        "verify": "✅ **Nimani tekshiring**",
        "ask": "❓ **Qanday savol bering**",
        "no_signal": (
            "Aniq xavf belgisi ko'rinmadi. Lekin bu kafolat emas: pul, kod yoki "
            "hujjat yuborishdan oldin manbani o'zingiz tekshiring."
        ),
        "limitation": (
            "ℹ️ **Nima noma'lum qoldi**\n"
            "Avvalo faqat javobda ko'rsatilgan belgilar va manbalarga tayandi. Bu odamni "
            "tekshirish yoki yakuniy xulosa emas."
        ),
        "fallback": (
            "Hozir javobni xavfsiz shaklda tayyorlay olmadim. Kodlarni aytmang, "
            "pul yubormang. Avval rasmiy ilova yoki o'zingiz topgan aloqa kanali "
            "orqali tekshiring."
        ),
    },
    Language.uz_cyrl: {
        "red_flags": "🚩 **Хавф белгилари**",
        "pattern": "**Қандай босим ишлатяпти:**",
        "verify": "✅ **Нимани текширинг**",
        "ask": "❓ **Қандай савол беринг**",
        "no_signal": (
            "Аниқ хавф белгиси кўринмади. Лекин бу кафолат эмас: пул, код ёки "
            "ҳужжат юборишдан олдин манбани ўзингиз текширинг."
        ),
        "limitation": (
            "ℹ️ **Нима номаълум қолди**\n"
            "Avvalo фақат жавобда кўрсатилган белгилар ва манбаларга таянди. Бу одамни "
            "текшириш ёки якуний хулоса эмас."
        ),
        "fallback": (
            "Ҳозир жавобни хавфсиз шаклда тайёрлай олмадим. Кодларни айтманг, "
            "пул юборманг. Аввал расмий илова ёки ўзингиз топган алоқа канали "
            "орқали текширинг."
        ),
    },
    Language.ru: {
        "red_flags": "🚩 **Тревожные признаки**",
        "pattern": "**Как на вас давят:**",
        "verify": "✅ **Что проверить**",
        "ask": "❓ **Что спросить**",
        "no_signal": (
            "Явных тревожных признаков не видно. Но это не гарантия: перед оплатой, "
            "кодом или документами проверьте источник самостоятельно."
        ),
        "limitation": (
            "ℹ️ **Что осталось неизвестным**\n"
            "Avvalo опирался только на признаки и источники, прямо указанные в ответе. "
            "Это не проверка личности и не окончательный вывод."
        ),
        "fallback": (
            "Сейчас не получилось подготовить безопасный ответ. Не сообщайте коды "
            "и не платите, пока не проверите ситуацию через официальное приложение "
            "или контакт, который нашли сами."
        ),
    },
}


def share_summary(rule_ids: list[str], language: Language | str) -> str:
    """Build a deterministic, content-free share warning from stored rule IDs."""

    resolved_language = _coerce_language(language)
    labels = _top_family_labels(rule_ids, resolved_language)
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
        Language.uz_latn: "Bugungi tekshiruvlar limiti tugadi. Ertaga yana urinib ko'ring.",
        Language.uz_cyrl: "Бугунги текширувлар лимити тугади. Эртага яна уриниб кўринг.",
        Language.ru: "На сегодня лимит проверок закончился. Попробуйте завтра.",
    },
    CheckStatus.empty_input: {
        Language.uz_latn: "Tekshirish uchun vaziyatga oid matn yoki havolani yuboring.",
        Language.uz_cyrl: "Текшириш учун вазиятга оид матн ёки ҳаволани юборинг.",
        Language.ru: "Пришлите текст или ссылку, относящиеся к ситуации.",
    },
    CheckStatus.low_ocr: {
        Language.uz_latn: "Rasm matnini aniq o'qiy olmadim. Muhim joyini xabar qilib yuboring.",
        Language.uz_cyrl: "Расм матнини аниқ ўқий олмадим. Муҳим жойини хабар қилиб юборинг.",
        Language.ru: (
            "Не получилось чётко прочитать текст на изображении. "
            "Пришлите важный фрагмент сообщением."
        ),
    },
    CheckStatus.timeout: {
        Language.uz_latn: "Tekshiruv cho'zilib ketdi. Qayta urinib ko'ring.",
        Language.uz_cyrl: "Текширув чўзилиб кетди. Қайта уриниб кўринг.",
        Language.ru: "Проверка затянулась. Попробуйте ещё раз.",
    },
    CheckStatus.llm_error: {
        Language.uz_latn: "Hozir bu vaziyatni tahlil qila olmadim. Qayta urinib ko'ring.",
        Language.uz_cyrl: "Ҳозир бу вазиятни таҳлил қила олмадим. Қайта уриниб кўринг.",
        Language.ru: (
            "Сейчас не получилось разобрать эту ситуацию. "
            "Попробуйте ещё раз."
        ),
    },
    CheckStatus.ocr_error: {
        Language.uz_latn: "Hozir bu rasmni qayta ishlay olmadim. Qayta urinib ko'ring.",
        Language.uz_cyrl: "Ҳозир бу расмни қайта ишлай олмадим. Қайта уриниб кўринг.",
        Language.ru: (
            "Сейчас не получилось обработать изображение. "
            "Попробуйте ещё раз."
        ),
    },
    CheckStatus.unsupported_media: {
        Language.uz_latn: "Matn yoki o'qilishi mumkin bo'lgan skrinshot yuboring.",
        Language.uz_cyrl: "Матн ёки ўқилиши мумкин бўлган скриншот юборинг.",
        Language.ru: "Пришлите текст или читаемый скриншот.",
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
    blocks.append(labels["limitation"])
    if copy.ask:
        blocks.append(_section(labels["ask"], copy.ask))
    return "\n\n".join(blocks)


def format_fallback(language: Language) -> str:
    """Return the localized safety fallback message."""

    return _HEADINGS[language]["fallback"]


def format_status_message(status: CheckStatus, language: Language) -> str:
    """Return the localized user-facing message for a non-success status."""

    return _STATUS_MESSAGES.get(status, _STATUS_MESSAGES[CheckStatus.unsupported_media])[
        language
    ]


def _section(title: str, bullets: list[str]) -> str:
    rendered = "\n".join(f"- {bullet}" for bullet in bullets)
    return f"{title}\n{rendered}"


def _coerce_language(language: Language | str) -> Language:
    try:
        return language if isinstance(language, Language) else Language(language)
    except ValueError:
        return Language.uz_latn


def _top_family_labels(rule_ids: list[str], language: Language) -> list[str]:
    by_rule = _rules_by_id()
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
def _rules_by_id():
    try:
        pack = load_rule_pack()
    except (FileNotFoundError, ValueError):
        return {}
    return {rule.id: rule for rule in pack.rules}


def _family_label(family: str, language: Language) -> str:
    localized = _FAMILY_LABELS.get(family, {})
    return localized.get(language) or family.replace("_", " ")
