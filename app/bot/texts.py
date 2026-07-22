"""All user-facing strings, keyed by (text key, language).

Three languages are supported: Uzbek (Latin), Uzbek (Cyrillic), and Russian.
Keeping every string here lets a test assert that no translation is missing.
"""

LANGUAGES = ("uz_latn", "uz_cyrl", "ru")
DEFAULT_LANGUAGE = "uz_latn"

# Shown on the language-selection buttons; each label is written in its own script.
LANGUAGE_LABELS = {
    "uz_latn": "O'zbek (lotin)",
    "uz_cyrl": "Ўзбек (кирил)",
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
        "uz_cyrl": (
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
        "uz_cyrl": _CHOOSE_LANGUAGE,
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
        "uz_cyrl": (
            "👋 Ассалому алайкум. Avvalo шубҳали хабар, скриншот ёки вазиятни "
            "жавоб бериш, пул юбориш ёки код/ҳужжат улашишдан олдин "
            "текшириб кўришга ёрдам беради.\n\n"
            "Қисқаси:\n"
            "• Мен одамни эмас, сиз юборган вазиятни таҳлил қиламан. «Хавфсиз» ёки "
            "«фирибгар» деган тамға қўймайман.\n"
            "• Жавобим маслаҳат ва текширув рўйхати. Бу юридик, молиявий ёки "
            "расмий хулоса эмас.\n"
            "• Юборган матн/расм фақат текширув учун ишлатилади ва 1 соат ичида "
            "ўчирилади.\n"
            "• Таҳлилга фақат минималлаштирилган матн юборилади: телефон, карта ва "
            "ҳаволалар токен билан алмаштирилади.\n"
            "• Хоҳлаган пайт /delete_my_data ёзиб маълумотларингизни ўчира оласиз. "
            "Батафсил: /privacy.\n\n"
            "Бошлаш учун «Розиман» ни босинг."
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
        "uz_cyrl": "✅ Розиман",
        "ru": "✅ Согласен",
    },
    "ready": {
        "uz_latn": "Tayyor. Shubhali xabar yoki skrinshotni yuboring — javob berishdan yoki to'lashdan oldin ko'rib chiqamiz.",
        "uz_cyrl": "Тайёр. Шубҳали хабар ёки скриншотни юборинг — жавоб беришдан ёки тўлашдан олдин кўриб чиқамиз.",
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
        "uz_cyrl": (
            "🔒 Махфийлик\n\n"
            "• Avvalo сиз юборган хабар, расм ёки вазиятни таҳлил қилади; одамлар ҳақида ҳукм чиқармайди.\n"
            "• Матн ва расмлар фақат текширув учун ишлатилади ва 1 соат ичида ўчирилади.\n"
            "• Таҳлилга телефон, карта ва ҳаволалари токен билан алмаштирилган минималлаштирилган матн юборилади.\n"
            "• Avvalo текширув рўйхати беради, лекин юридик ёки молиявий хулоса бермайди.\n"
            "• Маълумотларингизни ўчириш учун /delete_my_data юборинг."
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
        "uz_cyrl": "🗑 Маълумотларингиз ўчирилди. Қайта бошлаш учун /start юборинг.",
        "ru": "🗑 Данные удалены. Чтобы начать заново, отправьте /start.",
    },
    "need_consent": {
        "uz_latn": (
            "Avval /start ni bosing va «Roziman» tugmasini tasdiqlang. Shundan keyin xabarni tekshiraman."
        ),
        "uz_cyrl": (
            "Аввал /start ни босинг ва «Розиман» тугмасини тасдиқланг. Шундан кейин хабарни текшираман."
        ),
        "ru": (
            "Сначала отправьте /start и нажмите «Согласен». После этого я смогу проверить сообщение."
        ),
    },
    "consent_updated": {
        "uz_latn": "Maxfiylik shartlari yangilandi. Yangi matnni o'qib, yana rozilik bering.",
        "uz_cyrl": "Махфийлик шартлари янгиланди. Янги матнни ўқиб, яна розилик беринг.",
        "ru": "Условия конфиденциальности обновились. Прочитайте новый текст и подтвердите согласие ещё раз.",
    },
    "unsupported_input": {
        "uz_latn": "Tekshirish uchun xabar matni yoki skrinshot yuboring.",
        "uz_cyrl": "Текшириш учун хабар матни ёки скриншот юборинг.",
        "ru": "Пришлите текст сообщения или скриншот для проверки.",
    },
    "fb_saved": {
        "uz_latn": "Saqlandi",
        "uz_cyrl": "Сақланди",
        "ru": "Сохранено",
    },
    "feedback_expired": {
        "uz_latn": "Bu tugma eski tekshiruvga tegishli. Yangi natijadagi tugmalardan foydalaning.",
        "uz_cyrl": "Бу тугма эски текширувга тегишли. Янги натижадаги тугмалардан фойдаланинг.",
        "ru": "Эта кнопка относится к старой проверке. Используйте кнопки под новым результатом.",
    },
    "feedback_usefulness_first": {
        "uz_latn": "Avval shu natija foydali bo'lganini belgilang.",
        "uz_cyrl": "Аввал шу натижа фойдали бўлганини белгиланг.",
        "ru": "Сначала отметьте, был ли полезен этот результат.",
    },
    "fb_useful": {
        "uz_latn": "Foydali bo'ldi",
        "uz_cyrl": "Фойдали бўлди",
        "ru": "Помогло",
    },
    "fb_partly": {
        "uz_latn": "Qisman",
        "uz_cyrl": "Қисман",
        "ru": "Частично",
    },
    "fb_not_useful": {
        "uz_latn": "Foydali emas",
        "uz_cyrl": "Фойдали эмас",
        "ru": "Не помогло",
    },
    "fb_verify": {
        "uz_latn": "Tekshiraman",
        "uz_cyrl": "Текшираман",
        "ru": "Проверю",
    },
    "fb_stop": {
        "uz_latn": "To'xtab turaman",
        "uz_cyrl": "Тўхтаб тураман",
        "ru": "Подожду",
    },
    "fb_continue": {
        "uz_latn": "Davom etaman",
        "uz_cyrl": "Давом этаман",
        "ru": "Продолжу",
    },
    "fb_not_sure": {
        "uz_latn": "Ishonchim yo'q",
        "uz_cyrl": "Ишончим йўқ",
        "ru": "Пока не уверен",
    },
    "fb_share": {
        "uz_latn": "Avvalo'ni yuborish",
        "uz_cyrl": "Avvalo'ни юбориш",
        "ru": "Поделиться Avvalo",
    },
    "share_expired": {
        "uz_latn": (
            "Bu javobni ulashib bo'lmadi. "
            "Yangi tekshiruvdan keyin qayta urinib ko'ring."
        ),
        "uz_cyrl": (
            "Бу жавобни улашиб бўлмади. "
            "Янги текширувдан кейин қайта уриниб кўринг."
        ),
        "ru": (
            "Не удалось подготовить этот ответ для пересылки. "
            "Попробуйте после новой проверки."
        ),
    },
}


def t(key: str, language: str) -> str:
    """Return the string for *key* in *language*, falling back to the default."""

    table = TEXTS[key]
    return table.get(language) or table[DEFAULT_LANGUAGE]


def entry_text(language: str) -> str:
    """Return the post-consent ready message."""

    return t("ready", language)
