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
        "uz_latn": (
            "✅ Tayyor. Xabar yoki skrinshotni yuboring. Avvalo xavf belgilarini, "
            "nimani tekshirishni va nima deb so'rashni chiqarib beradi."
        ),
        "uz_cyrl": (
            "✅ Тайёр. Хабар ёки скриншотни юборинг. Avvalo хавф белгиларини, "
            "нимани текширишни ва нима деб сўрашни чиқариб беради."
        ),
        "ru": (
            "✅ Готово. Пришлите сообщение или скриншот. Avvalo покажет возможные "
            "риски, что проверить и что спросить."
        ),
    },
    "ready_family": {
        "uz_latn": "Tayyor. Shubhali xabar yoki skrinshotni yuboring — javob berishdan yoki to'lashdan oldin ko'rib chiqamiz.",
        "uz_cyrl": "Тайёр. Шубҳали хабар ёки скриншотни юборинг — жавоб беришдан ёки тўлашдан олдин кўриб чиқамиз.",
        "ru": "Готово. Пришлите сомнительное сообщение или скриншот — разберём до ответа или оплаты.",
    },
    "ready_merchants": {
        "uz_latn": (
            "Tayyor. Xaridor yuborgan chek, to'lov skrinshoti, yetkazish yoki qaytarim/refund "
            "xabarini yuboring. Tovarni berishdan oldin bank ilovasida nimani "
            "tekshirish kerakligini aytaman."
        ),
        "uz_cyrl": (
            "Тайёр. Харидор юборган чек, тўлов скриншоти, етказиш ёки қайтарим/refund "
            "хабарини юборинг. Товарни беришдан олдин банк иловасида нимани "
            "текшириш кераклигини айтаман."
        ),
        "ru": (
            "Готово. Пришлите чек, скриншот оплаты, доставку или возврат/refund от "
            "покупателя. Подскажу, что проверить в своём банке до передачи товара."
        ),
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
    "privacy_story_notice": {
        "uz_latn": (
            "\n\n• Agar tekshiruv foydali bo'lsa, Avvalo ixtiyoriy anonim hikoya so'rashi mumkin. "
            "Avval minimallashtirilgan matnni ko'rasiz; faqat alohida rozilik bossangiz, "
            "shu minimallashtirilgan matn asoschining ko'rib chiqishi uchun saqlanadi."
        ),
        "uz_cyrl": (
            "\n\n• Агар текширув фойдали бўлса, Avvalo ихтиёрий аноним ҳикоя сўраши мумкин. "
            "Аввал минималлаштирилган матнни кўрасиз; фақат алоҳида розилик боссангиз, "
            "шу минималлаштирилган матн асосчининг кўриб чиқиши учун сақланади."
        ),
        "ru": (
            "\n\n• Если проверка помогла, Avvalo может попросить добровольно поделиться "
            "анонимной историей. Сначала вы увидите минимизированный текст; только после "
            "отдельного согласия он сохранится для проверки основателем."
        ),
    },
    "story_invite": {
        "uz_latn": (
            "Bu foydali bo'lganidan xursandman. Boshqalarni ogohlantirish uchun nima "
            "bo'lganini anonim ulashasizmi? Avval minimallashtirilgan matnni ko'rsataman."
        ),
        "uz_cyrl": (
            "Бу фойдали бўлганидан хурсандман. Бошқаларни огоҳлантириш учун нима "
            "бўлганини аноним улашасизми? Аввал минималлаштирилган матнни кўрсатаман."
        ),
        "ru": (
            "Рад, что это помогло. Хотите анонимно поделиться тем, что произошло, "
            "чтобы предупредить других? Сначала я покажу минимизированный текст."
        ),
    },
    "story_start": {
        "uz_latn": "Anonim ulashish",
        "uz_cyrl": "Аноним улашиш",
        "ru": "Поделиться анонимно",
    },
    "story_no_thanks": {
        "uz_latn": "Yo'q, rahmat",
        "uz_cyrl": "Йўқ, раҳмат",
        "ru": "Нет, спасибо",
    },
    "story_prompt": {
        "uz_latn": (
            "Qisqa qilib nima bo'lganini yozing. Ism, telefon, karta yoki aniq manzil "
            "kiritmaslikka harakat qiling; Avvalo baribir minimallashtirib ko'rsatadi."
        ),
        "uz_cyrl": (
            "Қисқа қилиб нима бўлганини ёзинг. Исм, телефон, карта ёки аниқ манзил "
            "киритмасликка ҳаракат қилинг; Avvalo барибир минималлаштириб кўрсатади."
        ),
        "ru": (
            "Коротко напишите, что произошло. Постарайтесь не указывать имена, телефоны, "
            "карты или точный адрес; Avvalo всё равно минимизирует текст и покажет его вам."
        ),
    },
    "story_text_required": {
        "uz_latn": "Hikoya uchun faqat matn yuboring yoki bekor qiling.",
        "uz_cyrl": "Ҳикоя учун фақат матн юборинг ёки бекор қилинг.",
        "ru": "Для истории отправьте только текст или отмените.",
    },
    "story_too_long": {
        "uz_latn": "Hikoya juda uzun. Iltimos, {limit} belgigacha qisqartiring.",
        "uz_cyrl": "Ҳикоя жуда узун. Илтимос, {limit} белгичага қисқартиринг.",
        "ru": "История слишком длинная. Сократите её до {limit} символов.",
    },
    "story_preview_intro": {
        "uz_latn": "Saqlanishi mumkin bo'lgan minimallashtirilgan ko'rinish:",
        "uz_cyrl": "Сақланиши мумкин бўлган минималлаштирилган кўриниш:",
        "ru": "Минимизированная версия, которую можно сохранить:",
    },
    "story_preview_confirm": {
        "uz_latn": "Faqat shu matn ko'rib chiqish uchun saqlanadi. Rozimisiz?",
        "uz_cyrl": "Фақат шу матн кўриб чиқиш учун сақланади. Розимисиз?",
        "ru": "Только этот текст будет сохранён для проверки. Согласны?",
    },
    "story_publish": {
        "uz_latn": "Roziman, yuborish",
        "uz_cyrl": "Розиман, юбориш",
        "ru": "Согласен, отправить",
    },
    "story_cancel": {
        "uz_latn": "Bekor qilish",
        "uz_cyrl": "Бекор қилиш",
        "ru": "Отменить",
    },
    "story_saved": {
        "uz_latn": "Rahmat. Hikoya minimallashtirilgan holda ko'rib chiqish uchun yuborildi.",
        "uz_cyrl": "Раҳмат. Ҳикоя минималлаштирилган ҳолда кўриб чиқиш учун юборилди.",
        "ru": "Спасибо. Минимизированная история отправлена на проверку.",
    },
    "story_cancelled": {
        "uz_latn": "Bekor qilindi. Hikoya saqlanmadi.",
        "uz_cyrl": "Бекор қилинди. Ҳикоя сақланмади.",
        "ru": "Отменено. История не сохранена.",
    },
    "story_limit_reached": {
        "uz_latn": "Buguncha hikoya limiti tugadi. Rahmat, keyinroq qayta urinib ko'ring.",
        "uz_cyrl": "Бугунча ҳикоя лимити тугади. Раҳмат, кейинроқ қайта уриниб кўринг.",
        "ru": "На сегодня лимит историй исчерпан. Спасибо, попробуйте позже.",
    },
    "story_expired": {
        "uz_latn": "Bu hikoya oynasi eskirgan. Yangi tekshiruvdan keyin qayta urinib ko'ring.",
        "uz_cyrl": "Бу ҳикоя ойнаси эскирган. Янги текширувдан кейин қайта уриниб кўринг.",
        "ru": "Это окно истории устарело. Попробуйте после новой проверки.",
    },
}


def t(key: str, language: str) -> str:
    """Return the string for *key* in *language*, falling back to the default."""

    table = TEXTS[key]
    value = table.get(language) or table[DEFAULT_LANGUAGE]
    if key in {"privacy_notice", "privacy"}:
        story_table = TEXTS["privacy_story_notice"]
        return value + (story_table.get(language) or story_table[DEFAULT_LANGUAGE])
    return value


def entry_text(face_id: str, language: str) -> str:
    """Return the face-specific ready message, falling back to the generic one."""

    key = f"ready_{face_id}"
    return t(key, language) if key in TEXTS else t("ready", language)
