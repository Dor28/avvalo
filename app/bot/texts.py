"""All user-facing strings, keyed by (text key, language).

Two languages are supported: Uzbek (Latin) and Russian. Cyrillic-Uzbek input is
still understood by the engine, but replies are always Latin-script Uzbek.
Keeping every string here lets a test assert that no translation is missing.
"""

LANGUAGES = ("uz_latn", "ru")
DEFAULT_LANGUAGE = "uz_latn"

# Shown on the language-selection buttons; each label is written in its own script.
LANGUAGE_LABELS = {
    "uz_latn": "O'zbek (lotin)",
    "ru": "Русский",
}

_CHOOSE_LANGUAGE = "🌐 Tilni tanlang · Тилни танланг · Выберите язык"

TEXTS: dict[str, dict[str, str]] = {
    "start_intro": {
        "uz_latn": (
            "\U0001f1fa\U0001f1ff O'zbekcha\n"
            "Avvalo — shubhali vaziyatlarni tekshirishga yordam beradigan bot.\n"
            "Xabar, rasm yoki vaziyatni yuboring. Bot xavf belgilarini va nimani tekshirish kerakligini ko'rsatadi.\n\n"
            "\U0001f1f7\U0001f1fa Русский\n"
            "Avvalo — бот-помощник для проверки сомнительных ситуаций.\n"
            "Пришлите сообщение, изображение или опишите ситуацию. Бот покажет возможные риски и что нужно проверить."
        ),
        "ru": (
            "\U0001f1fa\U0001f1ff O'zbekcha\n"
            "Avvalo — shubhali vaziyatlarni tekshirishga yordam beradigan bot.\n"
            "Xabar, rasm yoki vaziyatni yuboring. Bot xavf belgilarini va nimani tekshirish kerakligini ko'rsatadi.\n\n"
            "\U0001f1f7\U0001f1fa Русский\n"
            "Avvalo — бот-помощник для проверки сомнительных ситуаций.\n"
            "Пришлите сообщение, изображение или опишите ситуацию. Бот покажет возможные риски и что нужно проверить."
        ),
    },
    "choose_language": {
        "uz_latn": _CHOOSE_LANGUAGE,
        "ru": _CHOOSE_LANGUAGE,
    },
    "privacy_notice": {
        "uz_latn": (
            "👋 Assalomu alaykum. Avvalo shubhali xabar, skrinshot yoki vaziyatni "
            "javob berish, pul yuborish yoki kod/hujjat ulashishdan oldin "
            "tekshirib ko'rishga yordam beradi.\n\n"
            "Qisqasi:\n"
            "• Men odamni emas, siz yuborgan vaziyatni tahlil qilaman. «Xavfsiz» yoki "
            "«firibgar» degan tamg'a qo'ymayman.\n"
            "• Javobim maslahat va tekshiruv ro'yxati. Bu yuridik, moliyaviy yoki "
            "rasmiy xulosa emas.\n"
            "• Yuborgan matn/rasm faqat tekshiruv uchun ishlatiladi va 1 soat ichida "
            "o'chiriladi.\n"
            "• Tahlilga faqat minimallashtirilgan matn ketadi: telefon, karta va "
            "havolalar token bilan almashtiriladi.\n"
            "• Xohlagan payt /delete_my_data yozib ma'lumotlaringizni o'chira olasiz. "
            "Batafsil: /privacy.\n\n"
            "Boshlash uchun «Roziman» ni bosing."
        ),
        "ru": (
            "👋 Avvalo помогает проверить сомнительное сообщение, скриншот или ситуацию "
            "до ответа, оплаты, отправки кода или документов.\n\n"
            "Коротко:\n"
            "• Я разбираю ситуацию, которую вы прислали, а не человека. Я не ставлю "
            "ярлыки «безопасно» или «мошенник».\n"
            "• Ответ — это подсказка и список проверок, а не юридическое, финансовое "
            "или официальное заключение.\n"
            "• Текст и изображения используются только для анализа и удаляются в течение 1 часа.\n"
            "• На анализ уходит только минимизированный текст: телефоны, карты и ссылки "
            "заменяются токенами.\n"
            "• Удалить свои данные можно в любой момент командой /delete_my_data. Подробнее: /privacy.\n\n"
            "Нажмите «Согласен», чтобы начать."
        ),
    },
    "btn_agree": {
        "uz_latn": "✅ Roziman",
        "ru": "✅ Согласен",
    },
    "ready": {
        "uz_latn": (
            "✅ Tayyor. Xabar yoki skrinshotni yuboring. Avvalo xavf belgilarini, "
            "nimani tekshirishni va nima deb so'rashni chiqarib beradi."
        ),
        "ru": (
            "✅ Готово. Пришлите сообщение или скриншот. Avvalo покажет возможные "
            "риски, что проверить и что спросить."
        ),
    },
    "ready_family": {
        "uz_latn": "Tayyor. Shubhali xabar yoki skrinshotni yuboring — javob berishdan yoki to'lashdan oldin ko'rib chiqamiz.",
        "ru": "Готово. Пришлите сомнительное сообщение или скриншот — разберём до ответа или оплаты.",
    },
    "privacy": {
        "uz_latn": (
            "🔒 Maxfiylik\n\n"
            "• Avvalo siz yuborgan xabar, rasm yoki vaziyatni tahlil qiladi; odamlar haqida hukm chiqarmaydi.\n"
            "• Matn va rasmlar faqat tekshiruv uchun ishlatiladi va 1 soat ichida o'chiriladi.\n"
            "• Tahlilga telefon, karta va havolalari token bilan almashtirilgan minimallashtirilgan matn ketadi.\n"
            "• Avvalo tekshiruv ro'yxati beradi, lekin yuridik yoki moliyaviy xulosa bermaydi.\n"
            "• Ma'lumotlaringizni o'chirish uchun /delete_my_data yuboring."
        ),
        "ru": (
            "🔒 Конфиденциальность\n\n"
            "• Avvalo анализирует сообщение, изображение или ситуацию, которую вы прислали; людей мы не оцениваем.\n"
            "• Текст и изображения используются только для проверки и удаляются в течение 1 часа.\n"
            "• На анализ уходит минимизированный текст: телефоны, карты и ссылки заменяются токенами.\n"
            "• Avvalo даёт список проверок, но не юридическое или финансовое заключение.\n"
            "• Чтобы удалить свои данные, отправьте /delete_my_data."
        ),
    },
    "data_deleted": {
        "uz_latn": "🗑 Ma'lumotlaringiz o'chirildi. Qayta boshlash uchun /start yuboring.",
        "ru": "🗑 Данные удалены. Чтобы начать заново, отправьте /start.",
    },
    "need_consent": {
        "uz_latn": (
            "Avval /start ni bosing va «Roziman» tugmasini tasdiqlang. Shundan keyin xabarni tekshiraman."
        ),
        "ru": (
            "Сначала отправьте /start и нажмите «Согласен». После этого я смогу проверить сообщение."
        ),
    },
    "consent_updated": {
        "uz_latn": "Maxfiylik shartlari yangilandi. Yangi matnni o'qib, yana rozilik bering.",
        "ru": "Условия конфиденциальности обновились. Прочитайте новый текст и подтвердите согласие ещё раз.",
    },
    "unsupported_input": {
        "uz_latn": "Tekshirish uchun xabar matni yoki skrinshot yuboring.",
        "ru": "Пришлите текст сообщения или скриншот для проверки.",
    },
    "fb_saved": {
        "uz_latn": "Saqlandi",
        "ru": "Сохранено",
    },
    "feedback_expired": {
        "uz_latn": "Bu tugma eski tekshiruvga tegishli. Yangi natijadagi tugmalardan foydalaning.",
        "ru": "Эта кнопка относится к старой проверке. Используйте кнопки под новым результатом.",
    },
    "feedback_usefulness_first": {
        "uz_latn": "Avval shu natija foydali bo'lganini belgilang.",
        "ru": "Сначала отметьте, был ли полезен этот результат.",
    },
    "fb_useful": {
        "uz_latn": "Foydali bo'ldi",
        "ru": "Помогло",
    },
    "fb_partly": {
        "uz_latn": "Qisman",
        "ru": "Частично",
    },
    "fb_not_useful": {
        "uz_latn": "Foydali emas",
        "ru": "Не помогло",
    },
    "fb_verify": {
        "uz_latn": "Tekshiraman",
        "ru": "Проверю",
    },
    "fb_stop": {
        "uz_latn": "To'xtab turaman",
        "ru": "Подожду",
    },
    "fb_continue": {
        "uz_latn": "Davom etaman",
        "ru": "Продолжу",
    },
    "fb_not_sure": {
        "uz_latn": "Ishonchim yo'q",
        "ru": "Пока не уверен",
    },
    "fb_share": {
        "uz_latn": "Avvalo'ni yuborish",
        "ru": "Поделиться Avvalo",
    },
    "share_expired": {
        "uz_latn": (
            "Bu javobni ulashib bo'lmadi. "
            "Yangi tekshiruvdan keyin qayta urinib ko'ring."
        ),
        "ru": (
            "Не удалось подготовить этот ответ для пересылки. "
            "Попробуйте после новой проверки."
        ),
    },
}


def normalize_language(language: str | None) -> str:
    """Coerce a stored language to one Avvalo still replies in.

    Consent rows and FSM state written before Uzbek Cyrillic was retired can
    still carry ``uz_cyrl``. Those users are simply answered in Latin-script
    Uzbek rather than being left stuck on a value the engine cannot build.
    """

    return language if language in LANGUAGES else DEFAULT_LANGUAGE


def t(key: str, language: str) -> str:
    """Return the string for *key* in *language*, falling back to the default."""

    table = TEXTS[key]
    return table.get(language) or table[DEFAULT_LANGUAGE]


def entry_text(face_id: str, language: str) -> str:
    """Return the face-specific ready message, falling back to the generic one."""

    key = f"ready_{face_id}"
    return t(key, language) if key in TEXTS else t("ready", language)
