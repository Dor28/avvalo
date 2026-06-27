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
    "choose_language": {
        "uz_latn": _CHOOSE_LANGUAGE,
        "uz_cyrl": _CHOOSE_LANGUAGE,
        "ru": _CHOOSE_LANGUAGE,
    },
    "privacy_notice": {
        "uz_latn": (
            "👋 Avvalo siz olgan xabar, skrinshot yoki vaziyatdagi xavf belgilarini — "
            "javob berish, to'lash yoki biror narsa ulashishdan oldin — ko'rishga yordam beradi.\n\n"
            "Bilib qo'ying:\n"
            "• Men «vaziyatni» tekshiraman, odamlarni emas. Hech qachon «xavfsiz» yoki «firibgar» "
            "demayman va ball qo'ymayman.\n"
            "• Men tushuntiruvchi vositaman — yuridik yoki moliyaviy maslahat emas, rasmiy tekshiruv ham emas.\n"
            "• Yuborgan narsangiz faqat tahlil uchun ishlatiladi va 1 soat ichida o'chiriladi. "
            "Matn va rasmlaringizni saqlamayman.\n"
            "• Sun'iy intellektga faqat minimallashtirilgan matn (telefon, karta va havolalar "
            "token bilan almashtirilgan) yuboriladi.\n"
            "• Ma'lumotlaringizni istalgan vaqtda /delete_my_data orqali o'chirishingiz mumkin. "
            "Batafsil: /privacy.\n\n"
            "Boshlash uchun «Roziman» tugmasini bosing."
        ),
        "uz_cyrl": (
            "👋 Avvalo сиз олган хабар, скриншот ёки вазиятдаги хавф белгиларини — "
            "жавоб бериш, тўлаш ёки бирор нарса улашишдан олдин — кўришга ёрдам беради.\n\n"
            "Билиб қўйинг:\n"
            "• Мен «вазиятни» текшираман, одамларни эмас. Ҳеч қачон «хавфсиз» ёки «фирибгар» "
            "демайман ва балл қўймайман.\n"
            "• Мен тушунтирувчи воситаман — юридик ёки молиявий маслаҳат эмас, расмий текширув ҳам эмас.\n"
            "• Юборган нарсангиз фақат таҳлил учун ишлатилади ва 1 соат ичида ўчирилади. "
            "Матн ва расмларингизни сақламайман.\n"
            "• Сунъий интеллектга фақат минималлаштирилган матн (телефон, карта ва ҳаволалар "
            "токен билан алмаштирилган) юборилади.\n"
            "• Маълумотларингизни исталган вақтда /delete_my_data орқали ўчиришингиз мумкин. "
            "Батафсил: /privacy.\n\n"
            "Бошлаш учун «Розиман» тугмасини босинг."
        ),
        "ru": (
            "👋 Avvalo помогает заметить тревожные признаки в полученном сообщении, скриншоте "
            "или ситуации — до того, как вы ответите, заплатите или чем-то поделитесь.\n\n"
            "Важно знать:\n"
            "• Я проверяю «ситуацию», а не людей. Я никогда не говорю «безопасно» или «мошенник» "
            "и не ставлю оценок.\n"
            "• Я инструмент-пояснение, а не юридическая или финансовая консультация и не официальная проверка.\n"
            "• То, что вы отправляете, используется только для анализа и удаляется в течение 1 часа. "
            "Я не храню ваши тексты и изображения.\n"
            "• Искусственному интеллекту передаётся только минимизированный текст (номера телефонов, "
            "карты и ссылки заменены токенами).\n"
            "• Вы можете удалить свои данные в любой момент командой /delete_my_data. Подробнее: /privacy.\n\n"
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
            "✅ Tayyor. Tekshirmoqchi bo'lgan xabar yoki skrinshotni yuboring "
            "yoki vaziyatni yozing."
        ),
        "uz_cyrl": (
            "✅ Тайёр. Текширмоқчи бўлган хабар ёки скриншотни юборинг "
            "ёки вазиятни ёзинг."
        ),
        "ru": (
            "✅ Готово. Пришлите сообщение или скриншот, который нужно проверить, "
            "либо опишите ситуацию."
        ),
    },
    "ready_family_shield": {
        "uz_latn": "Tayyor. Shubhali xabar, skrinshot yoki vaziyatni yuboring.",
        "uz_cyrl": "Тайёр. Шубҳали хабар, скриншот ёки вазиятни юборинг.",
        "ru": "Готово. Пришлите сомнительное сообщение, скриншот или ситуацию.",
    },
    "ready_seller_guard": {
        "uz_latn": (
            "Tayyor. Xaridor yuborgan to'lov cheki, yetkazish yoki refund so'rovini "
            "yuboring. Tovarni berishdan oldin tekshiramiz."
        ),
        "uz_cyrl": (
            "Тайёр. Харидор юборган тўлов чеки, етказиш ёки refund сўровини "
            "юборинг. Товарни беришдан олдин текширамиз."
        ),
        "ru": (
            "Готово. Пришлите чек оплаты, запрос на доставку или refund от "
            "покупателя. Проверим до того, как отдавать товар."
        ),
    },
    "privacy": {
        "uz_latn": (
            "🔒 Maxfiylik\n\n"
            "• Avvalo siz olgan kontent va vaziyatni tahlil qiladi, odamlar haqida hukm chiqarmaydi.\n"
            "• Yuborgan matn va rasmlaringiz faqat tahlil uchun ishlatiladi va 1 soat ichida "
            "o'chiriladi — ular saqlanmaydi.\n"
            "• Sun'iy intellektga faqat minimallashtirilgan matn yuboriladi (telefon, karta, "
            "havolalar tokenlar bilan almashtiriladi).\n"
            "• Avvalo tushuntirish vositasi — yuridik yoki moliyaviy maslahat emas; «xavfsiz» yoki "
            "«firibgar» degan xulosa bermaydi.\n"
            "• Barcha ma'lumotlaringizni o'chirish uchun /delete_my_data buyrug'ini yuboring."
        ),
        "uz_cyrl": (
            "🔒 Махфийлик\n\n"
            "• Avvalo сиз олган контент ва вазиятни таҳлил қилади, одамлар ҳақида ҳукм чиқармайди.\n"
            "• Юборган матн ва расмларингиз фақат таҳлил учун ишлатилади ва 1 соат ичида "
            "ўчирилади — улар сақланмайди.\n"
            "• Сунъий интеллектга фақат минималлаштирилган матн юборилади (телефон, карта, "
            "ҳаволалар токенлар билан алмаштирилади).\n"
            "• Avvalo тушунтириш воситаси — юридик ёки молиявий маслаҳат эмас; «хавфсиз» ёки "
            "«фирибгар» деган хулоса бермайди.\n"
            "• Барча маълумотларингизни ўчириш учун /delete_my_data буйруғини юборинг."
        ),
        "ru": (
            "🔒 Конфиденциальность\n\n"
            "• Avvalo анализирует полученный вами контент и ситуацию, не вынося суждений о людях.\n"
            "• Отправленные тексты и изображения используются только для анализа и удаляются "
            "в течение 1 часа — они не хранятся.\n"
            "• Искусственному интеллекту передаётся только минимизированный текст (телефоны, карты, "
            "ссылки заменяются токенами).\n"
            "• Avvalo — инструмент-пояснение, а не юридическая или финансовая консультация; "
            "он не выносит вердикт «безопасно» или «мошенник».\n"
            "• Чтобы удалить все свои данные, отправьте команду /delete_my_data."
        ),
    },
    "data_deleted": {
        "uz_latn": "🗑 Ma'lumotlaringiz o'chirildi. Qaytadan boshlash uchun /start yuboring.",
        "uz_cyrl": "🗑 Маълумотларингиз ўчирилди. Қайтадан бошлаш учун /start юборинг.",
        "ru": "🗑 Ваши данные удалены. Отправьте /start, чтобы начать заново.",
    },
    "need_consent": {
        "uz_latn": (
            "Iltimos, biror narsa yuborishdan oldin /start ni bosing va «Roziman» tugmasini tanlang."
        ),
        "uz_cyrl": (
            "Илтимос, бирор нарса юборишдан олдин /start ни босинг ва «Розиман» тугмасини танланг."
        ),
        "ru": (
            "Пожалуйста, отправьте /start и нажмите «Согласен», прежде чем отправлять что-либо на проверку."
        ),
    },
    "analysis_pending": {
        "uz_latn": "✅ Qabul qilindi. Tekshiruvchi hali sozlanmoqda — tahlil tez orada ishga tushadi.",
        "uz_cyrl": "✅ Қабул қилинди. Текширувчи ҳали созланмоқда — таҳлил тез орада ишга тушади.",
        "ru": "✅ Принято. Проверка ещё настраивается — анализ скоро заработает.",
    },
}


def t(key: str, language: str) -> str:
    """Return the string for *key* in *language*, falling back to the default."""

    table = TEXTS[key]
    return table.get(language) or table[DEFAULT_LANGUAGE]


def entry_text(face_id: str, language: str) -> str:
    """Return the face-specific ready message, falling back to the generic one."""

    key = f"ready_{face_id}"
    return t(key, language) if key in TEXTS else t("ready", language)
