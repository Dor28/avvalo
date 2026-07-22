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
            "Avvalo — harakatdan oldin shubhali vaziyatni tekshirishga yordam beradi.\n"
            "Xabar, rasm yoki vaziyatni yuboring: havola, QR-kod, to'lov so'rovi, "
            "taklif yoki hujjat ham bo'lishi mumkin. Avvalo nimaga e'tibor berish va "
            "nimani mustaqil tekshirishni ko'rsatadi.\n\n"
            "\U0001f1f7\U0001f1fa Русский\n"
            "Avvalo помогает разобраться в сомнительной ситуации до того, как вы начнёте действовать.\n"
            "Пришлите сообщение, изображение или опишите ситуацию: это может быть ссылка, "
            "QR-код, запрос на оплату, предложение или документ. Avvalo покажет, на что "
            "обратить внимание и что проверить самостоятельно."
        ),
        "ru": (
            "\U0001f1fa\U0001f1ff O'zbekcha\n"
            "Avvalo — harakatdan oldin shubhali vaziyatni tekshirishga yordam beradi.\n"
            "Xabar, rasm yoki vaziyatni yuboring: havola, QR-kod, to'lov so'rovi, "
            "taklif yoki hujjat ham bo'lishi mumkin. Avvalo nimaga e'tibor berish va "
            "nimani mustaqil tekshirishni ko'rsatadi.\n\n"
            "\U0001f1f7\U0001f1fa Русский\n"
            "Avvalo помогает разобраться в сомнительной ситуации до того, как вы начнёте действовать.\n"
            "Пришлите сообщение, изображение или опишите ситуацию: это может быть ссылка, "
            "QR-код, запрос на оплату, предложение или документ. Avvalo покажет, на что "
            "обратить внимание и что проверить самостоятельно."
        ),
    },
    "choose_language": {
        "uz_latn": _CHOOSE_LANGUAGE,
        "ru": _CHOOSE_LANGUAGE,
    },
    "privacy_notice": {
        "uz_latn": (
            "👋 Assalomu alaykum. Avvalo shubhali vaziyatni javob berish, pul to'lash, "
            "ilova o'rnatish yoki hujjat imzolash yoxud shaxsiy ma'lumot yuborishdan "
            "oldin tekshirishga yordam beradi.\n\n"
            "Qisqasi:\n"
            "• Avvalo siz yuborgan vaziyat, material yoki jarayonni tahlil qiladi — odamning "
            "obro'sini emas. «Xavfsiz», «firibgar» yoki yakuniy hukm bermaydi.\n"
            "• Javob e'tibor talab qiladigan belgilar, mustaqil tekshiruv qadamlari va "
            "beriladigan savollardan iborat. Bu yuridik, moliyaviy yoki rasmiy xulosa emas.\n"
            "• Yuborgan matn, rasm, havola va tayyorlangan javob saqlanmaydi hamda logga yozilmaydi.\n"
            "• Rasm faqat matnni aniqlash uchun qayta ishlanadi. Tashqi tahlil xizmatiga "
            "telefon, karta va havolalar token bilan almashtirilgan matn yuboriladi.\n"
            "• Xohlagan payt /delete_my_data yozib ma'lumotlaringizni o'chira olasiz. "
            "Batafsil: /privacy.\n\n"
            "Boshlash uchun «Roziman» ni bosing."
        ),
        "ru": (
            "👋 Avvalo помогает проверить сомнительную ситуацию до ответа, оплаты, "
            "установки приложения, подписания документа или передачи личных данных.\n\n"
            "Коротко:\n"
            "• Avvalo разбирает присланную ситуацию, материал или процесс, а не репутацию "
            "человека. Мы не ставим ярлыки «безопасно» или «мошенник» и не выносим вердикт.\n"
            "• В ответе будут признаки, требующие внимания, шаги независимой проверки и "
            "вопросы. Это не юридическое, финансовое или официальное заключение.\n"
            "• Присланные текст, изображение, ссылка и подготовленный ответ не сохраняются "
            "и не записываются в журналы.\n"
            "• Изображение используется только для распознавания текста. Сервис анализа "
            "получает текст, в котором телефоны, карты и ссылки заменены токенами.\n"
            "• Удалить свои данные можно в любой момент командой /delete_my_data. Подробнее: /privacy.\n\n"
            "Нажмите «Согласен», чтобы начать."
        ),
    },
    "btn_agree": {
        "uz_latn": "✅ Roziman",
        "ru": "✅ Согласен",
    },
    "ready": {
        "uz_latn": "Tayyor. Shubhali vaziyatga oid matn, havola yoki rasmni yuboring — harakat qilishdan oldin ko'rib chiqamiz.",
        "ru": "Готово. Пришлите текст, ссылку или изображение сомнительной ситуации — разберём до того, как вы начнёте действовать.",
    },
    "privacy": {
        "uz_latn": (
            "🔒 Maxfiylik\n\n"
            "• Avvalo vaziyat, material yoki jarayonni tahlil qiladi; odamning obro'siga baho bermaydi.\n"
            "• Yuborgan matn, rasm, havola va tayyorlangan javob saqlanmaydi hamda logga yozilmaydi.\n"
            "• Tashqi tahlil xizmatiga telefon, karta va havolalar token bilan almashtirilgan matn yuboriladi.\n"
            "• Avvalo mustaqil tekshiruv qadamlarini beradi, lekin yuridik, moliyaviy yoki rasmiy xulosa bermaydi.\n"
            "• Ma'lumotlaringizni o'chirish uchun /delete_my_data yuboring."
        ),
        "ru": (
            "🔒 Конфиденциальность\n\n"
            "• Avvalo разбирает ситуацию, материал или процесс, а не репутацию человека.\n"
            "• Присланные текст, изображение, ссылка и подготовленный ответ не сохраняются и не записываются в журналы.\n"
            "• Сервис анализа получает текст, в котором телефоны, карты и ссылки заменены токенами.\n"
            "• Avvalo даёт шаги независимой проверки, но не юридическое, финансовое или официальное заключение.\n"
            "• Чтобы удалить свои данные, отправьте /delete_my_data."
        ),
    },
    "data_deleted": {
        "uz_latn": "🗑 Ma'lumotlaringiz o'chirildi. Qayta boshlash uchun /start yuboring.",
        "ru": "🗑 Данные удалены. Чтобы начать заново, отправьте /start.",
    },
    "need_consent": {
        "uz_latn": (
            "Avval /start ni bosing va «Roziman» tugmasini tasdiqlang. Shundan keyin vaziyatni ko'rib chiqaman."
        ),
        "ru": (
            "Сначала отправьте /start и нажмите «Согласен». После этого я смогу разобрать ситуацию."
        ),
    },
    "consent_updated": {
        "uz_latn": "Maxfiylik shartlari yangilandi. Yangi matnni o'qib, yana rozilik bering.",
        "ru": "Условия конфиденциальности обновились. Прочитайте новый текст и подтвердите согласие ещё раз.",
    },
    "unsupported_input": {
        "uz_latn": "Tekshirish uchun matn, havola yoki o'qilishi mumkin bo'lgan rasm yuboring.",
        "ru": "Пришлите текст, ссылку или читаемое изображение ситуации.",
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
            "Ulashish uchun qisqa ogohlantirish tayyorlanmadi. "
            "Yangi tekshiruvdan keyin qayta urinib ko'ring."
        ),
        "ru": (
            "Не удалось подготовить краткое предупреждение для пересылки. "
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


def entry_text(language: str) -> str:
    """Return the post-consent ready message."""

    return t("ready", language)
