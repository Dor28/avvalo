"""Trilingual copy for the operator-only rule-override editor.

Operator-facing, but still trilingual: the founder and any future reviewer work
in whichever script they read fastest, and the project rule is that every
user-facing string exists in all three language forms.
"""

# ruff: noqa: E501, RUF001

# Cyrillic-Uzbek is retired as a *reply* language but is still matched on input,
# so pattern and alias groups keep it. ``LANGUAGE_LABELS`` covers reply languages
# only, hence this local map.
SCRIPT_LABELS = {
    "uz_latn": "O'zbek (lotin)",
    "uz_cyrl": "Ўзбек (кирилл)",
    "ru": "Русский",
}

# Stored taxonomy keys stay unchanged. These labels make the operator surface
# readable without turning persisted IDs into translated, unstable values.
FAMILY_PRESENTATION = {
    "uz_latn": {
        "credential_theft": {
            "label": "Kod va maxfiy ma'lumot",
            "summary": "SMS kodi, parol yoki hujjatdagi maxfiy ma'lumotni so'rash.",
        },
        "urgency_secrecy": {
            "label": "Shoshirish yoki sir saqlash",
            "summary": "Tez qaror qildirish yoki boshqalarga aytmaslikka undash.",
        },
        "authority_impersonation": {
            "label": "Tashkilot yoki yaqin odam nomidan yozish",
            "summary": (
                "Bank, davlat idorasi, yetkazib berish xizmati, ish beruvchi yoki "
                "yaqin odam sifatida yozish."
            ),
        },
        "upfront_payment": {
            "label": "Oldindan to'lov",
            "summary": "Tovar, suhbat yoki shartnomadan oldin pul yoki depozit so'rash.",
        },
        "verification_avoidance": {
            "label": "Mustaqil tekshiruvdan qochish",
            "summary": "Rasmiy kanal, uchrashuv yoki videoqo'ng'iroq orqali tekshirishga yo'l bermaslik.",
        },
        "implausible_promise": {
            "label": "Haddan tashqari yaxshi va'da",
            "summary": "Odatdagidan juda yuqori daromad, juda arzon narx yoki oson foyda va'dasi.",
        },
        "suspicious_link_qr": {
            "label": "Shubhali havola yoki QR",
            "summary": "Yuborilgan havola yoki QR orqali kirish yoxud to'lov qilishga undash.",
        },
        "receipt_inconsistency": {
            "label": "To'lovdagi nomuvofiqlik",
            "summary": "Pul tushgani haqidagi gap bilan qabul qiluvchi hisobdagi holat mos kelmasligi.",
        },
        "edited_screenshot_hint": {
            "label": "Skrinshotni to'lov isboti deb ko'rsatish",
            "summary": "Chek yoki skrinshotni pul haqiqatan tushganining o'rniga ko'rsatish.",
        },
        "amount_mismatch": {
            "label": "Summa yoki qaytarim mos kelmasligi",
            "summary": "Tasdiqlanmagan ortiqcha to'lov uchun alohida pul qaytarishni so'rash.",
        },
        "fake_courier_refund": {
            "label": "Pul tushmasdan jo'natishga shoshirish",
            "summary": "To'lov tasdiqlanmasdan tovarni berish yoki jo'natishga bosim qilish.",
        },
    },
    "ru": {
        "credential_theft": {
            "label": "Коды и секретные данные",
            "summary": "Запрос кода из SMS, пароля или секретных данных из документов.",
        },
        "urgency_secrecy": {
            "label": "Срочность или секретность",
            "summary": "Давление с целью ускорить решение или просьба никому не рассказывать.",
        },
        "authority_impersonation": {
            "label": "Сообщение от имени организации или близкого",
            "summary": (
                "Сообщение от имени банка, госоргана, службы доставки, работодателя "
                "или близкого человека."
            ),
        },
        "upfront_payment": {
            "label": "Предоплата",
            "summary": "Просьба заплатить или внести депозит до товара, собеседования или договора.",
        },
        "verification_avoidance": {
            "label": "Уход от независимой проверки",
            "summary": "Отказ от официального канала, встречи или видеозвонка для проверки.",
        },
        "implausible_promise": {
            "label": "Слишком выгодное обещание",
            "summary": "Необычно высокий доход, слишком низкая цена или обещание лёгкой прибыли.",
        },
        "suspicious_link_qr": {
            "label": "Подозрительная ссылка или QR",
            "summary": "Подталкивание к входу или оплате через присланную ссылку либо QR-код.",
        },
        "receipt_inconsistency": {
            "label": "Несостыковка в оплате",
            "summary": "Рассказ о переводе не совпадает с тем, что видно на счёте получателя.",
        },
        "edited_screenshot_hint": {
            "label": "Скриншот как доказательство оплаты",
            "summary": "Чек или скриншот показывают вместо подтверждённого поступления денег.",
        },
        "amount_mismatch": {
            "label": "Несовпадение суммы или возврата",
            "summary": "Просьба отдельно вернуть якобы лишний, но ещё не подтверждённый перевод.",
        },
        "fake_courier_refund": {
            "label": "Отправка товара до поступления денег",
            "summary": "Давление с целью забрать или отправить товар до подтверждения оплаты.",
        },
    },
}

MESSAGE_LABELS = {
    "uz_latn": {
        "otp_request": "SMS kodi yoki maxfiy iborani so'rash",
        "secret_request": "Parol yoki hujjat ma'lumotini so'rash",
        "urgency_deadline": "Shoshiltirish va sun'iy muddat",
        "secrecy": "Hech kimga aytmaslikni so'rash",
        "authority": "Tashkilot yoki yaqin odam nomidan yozish",
        "upfront_payment": "Oldindan pul so'rash",
        "verification_avoidance": "Mustaqil tekshiruvdan qochish",
        "implausible_promise": "Haddan tashqari yaxshi va'da",
        "suspicious_link": "Havola yoki QR orqali to'lovga undash",
        "receipt_inconsistency": "To'lov haqidagi gaplarda nomuvofiqlik",
        "edited_screenshot": "Skrinshotni to'lov isboti deb ko'rsatish",
        "amount_mismatch": "Ortiqcha to'lovni qaytarishni so'rash",
        "ship_before_confirm": "Pul tushmasdan tovarni jo'natishga shoshirish",
    },
    "ru": {
        "otp_request": "Запрос кода из SMS или секретной фразы",
        "secret_request": "Запрос пароля или данных из документов",
        "urgency_deadline": "Давление срочностью и искусственный срок",
        "secrecy": "Просьба никому не рассказывать",
        "authority": "Сообщение от имени организации или близкого",
        "upfront_payment": "Просьба о предоплате",
        "verification_avoidance": "Уход от независимой проверки",
        "implausible_promise": "Слишком выгодное обещание",
        "suspicious_link": "Оплата или вход через ссылку либо QR",
        "receipt_inconsistency": "Несостыковка в рассказе об оплате",
        "edited_screenshot": "Скриншот как доказательство оплаты",
        "amount_mismatch": "Просьба вернуть якобы лишний перевод",
        "ship_before_confirm": "Отправка товара до поступления денег",
    },
}

SEVERITY_PRESENTATION = {
    "uz_latn": {
        1: {
            "label": "Qo'shimcha belgi",
            "hint": "Kontekst beradi, lekin o'zi alohida xavf belgisini majburlamaydi.",
        },
        2: {
            "label": "Muhim ogohlantirish",
            "hint": "Qoida ishlasa, javob bu holatni xavf belgisi sifatida yoritishi kerak.",
        },
        3: {
            "label": "Kuchli ogohlantirish",
            "hint": "Muhim belgilar orasida yuqoriroq turadi va javobda yoritilishi kerak.",
        },
    },
    "ru": {
        1: {
            "label": "Дополнительный признак",
            "hint": "Даёт контекст, но сам по себе не требует отдельного тревожного признака.",
        },
        2: {
            "label": "Важное предупреждение",
            "hint": "Если правило сработало, ответ должен отразить это как тревожный признак.",
        },
        3: {
            "label": "Сильное предупреждение",
            "hint": "Стоит выше других важных признаков и должно быть отражено в ответе.",
        },
    },
}

_ERRORS = {
    "uz_latn": {
        "invalid_face": "Noma'lum tekshiruv yuzasi.",
        "invalid_rule_id": "Qoida ID'si `fs.oila.nom` ko'rinishida bo'lishi kerak.",
        "invalid_family": "Oila nomi faqat kichik lotin harflari va pastki chiziqdan iborat bo'lsin.",
        "invalid_message_key": "Xabar kaliti faqat kichik lotin harflari va pastki chiziqdan iborat bo'lsin.",
        "invalid_description": "Izoh bo'sh bo'lmasligi va 400 belgidan oshmasligi kerak.",
        "invalid_severity": "Jiddiylik darajasi 1 va 3 orasida bo'lsin.",
        "invalid_emits_signal": "Signal nomi noto'g'ri.",
        "invalid_patterns": "Shablonlar ro'yxati noto'g'ri.",
        "invalid_pattern_language": "Faqat uz_latn, uz_cyrl va ru tillari qo'llab-quvvatlanadi.",
        "pattern_too_long": "Shablon juda uzun (120 belgidan ko'p).",
        "pattern_too_short": "Shablon juda qisqa — kamida 3 belgi bo'lsin, aks holda hamma narsaga mos keladi.",
        "invalid_regex": "Regex xato: u kompilyatsiya qilinmadi.",
        "empty_regex": "`regex:` dan keyin ifoda yozilmagan.",
        "no_patterns": "Kamida bitta shablon kiriting yoki qoidani o'chirilgan deb belgilang.",
        "duplicate_rule": "Bu qoida ID'si allaqachon mavjud.",
    },
    "ru": {
        "invalid_face": "Неизвестная поверхность проверки.",
        "invalid_rule_id": "ID правила должен быть вида `fs.семейство.имя`.",
        "invalid_family": "Имя семейства — только строчные латинские буквы и подчёркивание.",
        "invalid_message_key": "Ключ сообщения — только строчные латинские буквы и подчёркивание.",
        "invalid_description": "Описание не должно быть пустым и длиннее 400 символов.",
        "invalid_severity": "Уровень важности должен быть от 1 до 3.",
        "invalid_emits_signal": "Некорректное имя сигнала.",
        "invalid_patterns": "Некорректный список шаблонов.",
        "invalid_pattern_language": "Поддерживаются только uz_latn, uz_cyrl и ru.",
        "pattern_too_long": "Шаблон слишком длинный (более 120 символов).",
        "pattern_too_short": "Шаблон слишком короткий — минимум 3 символа, иначе он совпадёт почти со всем.",
        "invalid_regex": "Ошибка regex: выражение не компилируется.",
        "empty_regex": "После `regex:` не указано выражение.",
        "no_patterns": "Добавьте хотя бы один шаблон или отметьте правило отключённым.",
        "duplicate_rule": "Правило с таким ID уже существует.",
    },
}

RULES_COPY = {
    "uz_latn": {
        "title": "Qoida shablonlari",
        "subtitle": (
            "Bu shablonlar ochiq repozitoriyda emas, ma'lumotlar bazasida saqlanadi. "
            "Ular paketdagi asosiy qoidalar ustiga ID bo'yicha qo'shiladi."
        ),
        "new": "Yangi qoida",
        "empty": "Hozircha qo'shimcha qoida yo'q. Tekshiruv paketdagi asosiy qoidalar bo'yicha ishlaydi.",
        "edit": "Tahrirlash",
        "delete": "O'chirish",
        "delete_confirm": "Bu qoidani o'chirsangiz, paketdagi asosiy qoida yana kuchga kiradi.",
        "back": "Ro'yxatga qaytish",
        "save": "Saqlash",
        "test": "Sinab ko'rish",
        "status_active": "Faol",
        "status_disabled": "O'chirilgan",
        "updated": "Yangilandi:",
        "category_label": "Vaziyat turi",
        "category_hint": "Qoida qaysi turdagi shubhali vaziyatga tegishli ekanini tanlang.",
        "rule_name_label": "Qoida nomi (texnik ID)",
        "rule_id_hint": (
            "Kichik lotin harflarida noyob nom yozing, masalan `fs.authority.new_number`. "
            "Paketdagi mavjud ID kiritilsa, o'sha qoida almashtiriladi."
        ),
        "description_label": "Model uchun qisqa izoh (ingliz tilida)",
        "description_hint": (
            "Vaziyatda nima sodir bo'layotganini bitta neytral gapda yozing. "
            "Odamga hukm bermang."
        ),
        "severity_label": "Ogohlantirish darajasi",
        "severity_hint": "Daraja Avvalo bu belgini javobda qanday ishlatishini belgilaydi.",
        "form_title": "Qoidani sozlash",
        "form_subtitle": "Vaziyatni tanlang, iboralarni kiriting va saqlashdan oldin sinab ko'ring.",
        "main_section_title": "Qoida nimani aniqlaydi?",
        "main_section_hint": "Avval vaziyat turini va bu belgining ahamiyatini belgilang.",
        "patterns_section_title": "Qaysi iboralar qoidani ishga tushiradi?",
        "patterns_section_hint": "Foydalanuvchi xabarida uchrashi mumkin bo'lgan aniq iboralarni kiriting.",
        "technical_title": "Texnik sozlamalar",
        "technical_hint": "Odatda bu maydonlarni o'zgartirish shart emas.",
        "technical_details": "Texnik ma'lumotlar",
        "technical_family": "Saqlangan vaziyat turi",
        "technical_severity": "Saqlangan daraja",
        "technical_description": "Modelga uzatiladigan izoh",
        "message_key_label": "Ichki xabar kaliti (ixtiyoriy)",
        "message_key_hint": "Bo'sh qoldirilsa, qoida ID'sining oxirgi qismidan olinadi.",
        "emits_signal_label": "Ichki signal (ixtiyoriy)",
        "emits_signal_hint": "Faqat mavjud strukturaviy signalga ulash kerak bo'lsa kiriting.",
        "disabled_label": "Bu qoidani o'chirish",
        "disabled_hint": "Belgilansa, shu ID'li asosiy qoida ishlamaydi.",
        "patterns_label": "Ishga tushiruvchi iboralar — {language}",
        "patterns_hint": (
            "Har qatorda bitta aniq ibora yozing. Katta-kichik harf farq qilmaydi. "
            "Murakkab moslik kerak bo'lsa, qatorni `regex:` bilan boshlang."
        ),
        "sample_title": "Sinov matni",
        "sample_hint": (
            "Saqlashdan oldin sinab ko'ring. Xato shablon barcha foydalanuvchilar uchun "
            "aniqlashni sezdirmasdan buzadi."
        ),
        "sample_label": "Namuna matn",
        "preview_title": "Sinov natijasi",
        "preview_match": "Qoida ishga tushdi. Mos kelgan shablonlar:",
        "preview_no_match": "Qoida ishga tushmadi — bu matnda hech bir shablon mos kelmadi.",
        "baseline_note": "Paketdagi asosiy qoidalar: {count} ta. Faol qoidalar: {active} ta.",
        "baseline_pill": "tayyor qoida",
        "baseline_edit": "Ustiga yozish",
        "baseline_row_hint": "Avvalo bilan birga kelgan tayyor qoida. Tahrirlansa, saqlangan nusxa uning o'rnini oladi.",
        "errors": _ERRORS["uz_latn"],
    },
    "ru": {
        "title": "Шаблоны правил",
        "subtitle": (
            "Эти шаблоны хранятся в базе данных, а не в открытом репозитории. "
            "Они накладываются на базовый пакет правил по ID."
        ),
        "new": "Новое правило",
        "empty": "Пока нет дополнительных правил. Проверка идёт по базовому пакету.",
        "edit": "Редактировать",
        "delete": "Удалить",
        "delete_confirm": "Если удалить это правило, снова вступит в силу базовое правило из пакета.",
        "back": "Вернуться к списку",
        "save": "Сохранить",
        "test": "Проверить",
        "status_active": "Активно",
        "status_disabled": "Отключено",
        "updated": "Обновлено:",
        "category_label": "Тип ситуации",
        "category_hint": "Выберите, к какому типу сомнительной ситуации относится правило.",
        "rule_name_label": "Название правила (технический ID)",
        "rule_id_hint": (
            "Введите уникальное имя строчными латинскими буквами, например "
            "`fs.authority.new_number`. Существующий ID из пакета заменит базовое правило."
        ),
        "description_label": "Краткое пояснение для модели (на английском)",
        "description_hint": (
            "Одним нейтральным предложением опишите, что происходит в ситуации. "
            "Не выносите суждение о человеке."
        ),
        "severity_label": "Уровень предупреждения",
        "severity_hint": "Уровень определяет, как Avvalo использует этот признак в ответе.",
        "form_title": "Настройка правила",
        "form_subtitle": "Выберите ситуацию, добавьте фразы и проверьте правило перед сохранением.",
        "main_section_title": "Что должно обнаруживать правило?",
        "main_section_hint": "Сначала выберите тип ситуации и важность этого признака.",
        "patterns_section_title": "Какие фразы запускают правило?",
        "patterns_section_hint": "Добавьте точные фразы, которые могут встретиться в сообщении пользователя.",
        "technical_title": "Технические настройки",
        "technical_hint": "Обычно эти поля менять не нужно.",
        "technical_details": "Технические данные",
        "technical_family": "Сохранённый тип ситуации",
        "technical_severity": "Сохранённый уровень",
        "technical_description": "Пояснение для модели",
        "message_key_label": "Внутренний ключ сообщения (необязательно)",
        "message_key_hint": "Если оставить пустым, будет взята последняя часть ID правила.",
        "emits_signal_label": "Внутренний сигнал (необязательно)",
        "emits_signal_hint": "Заполняйте только для привязки к существующему структурному сигналу.",
        "disabled_label": "Отключить это правило",
        "disabled_hint": "Если отмечено, базовое правило с этим ID не сработает.",
        "patterns_label": "Фразы для срабатывания — {language}",
        "patterns_hint": (
            "По одной точной фразе в строке. Регистр не учитывается. Для сложного "
            "совпадения начните строку с `regex:`."
        ),
        "sample_title": "Тестовый текст",
        "sample_hint": (
            "Проверьте перед сохранением. Ошибочный шаблон незаметно ломает "
            "детекцию для всех пользователей."
        ),
        "sample_label": "Пример текста",
        "preview_title": "Результат проверки",
        "preview_match": "Правило сработало. Совпавшие шаблоны:",
        "preview_no_match": "Правило не сработало — ни один шаблон не совпал с этим текстом.",
        "baseline_note": "Базовых правил в пакете: {count}. Активных правил: {active}.",
        "baseline_pill": "готовое правило",
        "baseline_edit": "Переопределить",
        "baseline_row_hint": "Готовое правило Avvalo. После редактирования сохранённая копия заменит его.",
        "errors": _ERRORS["ru"],
    },
}
