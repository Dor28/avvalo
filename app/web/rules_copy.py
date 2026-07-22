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
        "rule_id_label": "Qoida ID'si",
        "rule_id_hint": "Paketdagi mavjud ID kiritilsa, o'sha qoida almashtiriladi. Yangi ID yangi qoida qo'shadi.",
        "family_label": "Oila",
        "description_label": "Izoh (ingliz tilida, modelga fakt sifatida uzatiladi)",
        "message_key_label": "Xabar kaliti",
        "severity_label": "Jiddiylik (1–3)",
        "emits_signal_label": "Signal (ixtiyoriy)",
        "disabled_label": "Bu qoidani o'chirish",
        "disabled_hint": "Belgilansa, shu ID'li asosiy qoida ishlamaydi.",
        "patterns_label": "Shablonlar — {language}",
        "patterns_hint": (
            "Har bir qatorda bitta shablon. Oddiy matn kichik harfga keltirilib qidiriladi. "
            "Regex uchun qatorni `regex:` bilan boshlang."
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
        "rule_id_label": "ID правила",
        "rule_id_hint": "Существующий ID из пакета заменит это правило. Новый ID добавит правило.",
        "family_label": "Семейство",
        "description_label": "Описание (на английском, передаётся модели как факт)",
        "message_key_label": "Ключ сообщения",
        "severity_label": "Важность (1–3)",
        "emits_signal_label": "Сигнал (необязательно)",
        "disabled_label": "Отключить это правило",
        "disabled_hint": "Если отмечено, базовое правило с этим ID не сработает.",
        "patterns_label": "Шаблоны — {language}",
        "patterns_hint": (
            "По одному шаблону в строке. Обычный текст ищется без учёта регистра. "
            "Для регулярного выражения начните строку с `regex:`."
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
        "errors": _ERRORS["ru"],
    },
}
