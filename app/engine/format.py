"""Final user-facing message formatting."""

from app.engine.types import CheckStatus, DraftOutput, Language

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
