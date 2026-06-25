"""Final user-facing message formatting."""

from app.engine.types import DraftOutput, Language

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
