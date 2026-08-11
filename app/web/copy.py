"""Bilingual copy for the public web channel.

Split out of ``app.web.routes`` so the route handlers and the wording can be
edited independently: three admin modules only ever wanted ``WEB_COPY`` and had
to import the whole routes module to get it. Mirrors the existing
``editorial_copy`` / ``rules_copy`` / ``knowledge_copy`` modules.

Public copy is `uz_latn` + `ru` only — Uzbek replies are Latin-script even when
the submitted content is Cyrillic-Uzbek (technical plan §8).
"""

WEB_COPY = {
    "uz_latn": {
        "html_lang": "uz-Latn",
        "privacy_link": "Maxfiylik",
        "language_label": "Til",
        "nav_label": "Asosiy bo‘limlar",
        "nav_check": "Tekshiruv",
        "nav_cases": "Holatlar",
        "trust_label": "Ishonch",
        "skip_to_check": "Tekshiruvga o‘tish",
        "brand_tagline": "Avval tekshiring, keyin harakat qiling",
        "hero_kicker": "Qaror qilishdan oldin",
        "use_cases_label": "Nimani tekshirish mumkin",
        "composer_kicker": "Anonim tekshiruv",
        "composer_title": "Vaziyatni tasvirlab bering",
        "composer_body": (
            "Matn yoki havolani kiriting. Kerak bo‘lsa, skrinshot yoki rasm qo‘shing. "
            "Bu to‘lov so‘rovi, taklif, hujjat yoki yozishma bo‘lishi mumkin."
        ),
        "input_hint": "SMS kod, parol va karta ma’lumotlarini yashiring.",
        "outcome_title": "Avvalo qanday yordam beradi",
        "outcome_body": (
            "Javob tushunarli va amaliy bo‘ladi: vaziyatda nimaga e’tibor berish "
            "va keyin nima qilish kerak."
        ),
        "outcomes": [
            {
                "title": "Muhim belgilar",
                "body": "Shoshiltirish, bosim va bir-biriga mos kelmaydigan tafsilotlar.",
            },
            {
                "title": "Keyingi qadamlar",
                "body": "Manbani mustaqil tekshirish va o‘zingizni himoya qilish yo‘llari.",
            },
            {
                "title": "Nima noaniq qoladi",
                "body": "Hali tasdiqlanmagan ma’lumotlar.",
            },
            {
                "title": "Nimani so‘rash",
                "body": "Suhbatdosh yoki tashkilotga beriladigan qisqa savollar.",
            },
        ],
        "boundary_title": "Vaziyatni tekshiring, odamni emas",
        "boundary_body": (
            "Avvalo vaziyatni tahlil qiladi, odam yoki tashkilotga baho bermaydi. "
            "Ma’lumotni rasmiy manbadan o‘zingiz tekshiring: Avvalo tavsiya beradi, "
            "natijani kafolatlamaydi."
        ),
        "footer_note": "Shoshilmang. Avval tekshiring, keyin harakat qiling.",
        "result_ready": "Javob tayyor",
        "result_title": "Vaziyat bo‘yicha qadamlar",
        "title": "Avvalo",
        "privacy_title": "Maxfiylik",
        "consent_label": "Maxfiylik shartlarini o‘qidim va roziman",
        "image_label": "Skrinshot yoki rasm",
        "optional_label": "ixtiyoriy",
        "choose_file": "Rasm tanlash",
        "clear_file": "Faylni olib tashlash",
        "submit": "Vaziyatni tekshirish",
        "checking": "Tekshirilmoqda...",
        "result_error_title": "Hozir tekshira olmadik",
        "empty_error": "Matn kiriting yoki matni aniq ko‘rinadigan rasm yuklang.",
        "too_long_error": "Matn juda uzun. Uni qisqartirib, qayta yuboring.",
        "consent_error": "Avval maxfiylik shartlariga rozilik bering.",
        "check": {
            "name": "Vaziyat tekshiruvi",
            "headline": "Shubha bormi? Avvalo'ga yuboring.",
            "subhead": (
                "Shubhali xabar, havola, QR-kod, to‘lov so‘rovi yoki hujjatni yuboring. "
                "Avvalo nimaga e’tibor berish va keyin nima qilishni tushuntiradi."
            ),
            "prompt": "Matn, havola yoki vaziyat tavsifi",
            "textarea_placeholder": (
                "Masalan: menga to‘lov skrinshotini yuborib, pul tushmasidan oldin "
                "tovarni berishimni so‘rashyapti..."
            ),
            "image_hint": "Yozishma, chek, QR-kod yoki hujjat rasmda aniq ko‘rinsin.",
            "use_cases": [
                "Xabar yoki yozishma",
                "Havola yoki QR-kod",
                "To‘lov skrinshoti yoki so‘rovi",
                "Ish yoki hamkorlik taklifi",
                "Hujjat yoki so‘rov",
            ],
            "trust": [
                "Odamni emas, vaziyatni tekshiradi",
                "Hukm chiqarmaydi, tekshiruv qadamlarini ko‘rsatadi",
                "Tavsiya beradi, natijani kafolatlamaydi",
                "Matn, rasm va javob saqlanmaydi",
            ],
        },
    },
    "ru": {
        "html_lang": "ru",
        "privacy_link": "Конфиденциальность",
        "language_label": "Язык",
        "nav_label": "Основные разделы",
        "nav_check": "Проверка",
        "nav_cases": "Кейсы",
        "trust_label": "Доверие",
        "skip_to_check": "Перейти к проверке",
        "brand_tagline": "Сначала проверьте, потом действуйте",
        "hero_kicker": "Перед тем как действовать",
        "use_cases_label": "Что можно проверить",
        "composer_kicker": "Анонимная проверка",
        "composer_title": "Опишите ситуацию",
        "composer_body": (
            "Вставьте текст или ссылку. При необходимости добавьте скриншот или фото. "
            "Это может быть запрос на оплату, предложение, документ или переписка."
        ),
        "input_hint": "Скройте SMS-коды, пароли и полные данные карты.",
        "outcome_title": "Чем поможет Avvalo",
        "outcome_body": (
            "Ответ будет понятным и практичным: на что обратить внимание "
            "и что делать дальше."
        ),
        "outcomes": [
            {
                "title": "Важные признаки",
                "body": "Спешка, давление и несостыковки в деталях.",
            },
            {
                "title": "Следующие шаги",
                "body": "Как самостоятельно проверить источник и защитить себя.",
            },
            {
                "title": "Что пока неясно",
                "body": "Данные, которые пока нельзя подтвердить.",
            },
            {
                "title": "Что спросить",
                "body": "Короткие вопросы собеседнику или организации.",
            },
        ],
        "boundary_title": "Проверяйте ситуацию, а не человека",
        "boundary_body": (
            "Avvalo разбирает ситуацию, а не оценивает человека или организацию. "
            "Проверяйте данные по официальным источникам самостоятельно: Avvalo даёт "
            "рекомендации, но не гарантирует результат."
        ),
        "footer_note": "Не спешите. Сначала проверьте, потом действуйте.",
        "result_ready": "Ответ готов",
        "result_title": "Шаги по вашей ситуации",
        "title": "Avvalo",
        "privacy_title": "Конфиденциальность",
        "consent_label": "Я прочитал условия конфиденциальности и согласен",
        "image_label": "Скриншот или фото",
        "optional_label": "необязательно",
        "choose_file": "Выбрать фото",
        "clear_file": "Убрать файл",
        "submit": "Проверить ситуацию",
        "checking": "Проверяем...",
        "result_error_title": "Сейчас не удалось проверить",
        "empty_error": "Вставьте текст или загрузите изображение с читаемым текстом.",
        "too_long_error": "Текст получился слишком длинным. Сократите его и отправьте ещё раз.",
        "consent_error": "Сначала примите условия конфиденциальности.",
        "check": {
            "name": "Проверка ситуации",
            "headline": "Есть сомнения? Отправьте в Avvalo.",
            "subhead": (
                "Отправьте подозрительное сообщение, ссылку, QR-код, запрос на оплату или "
                "документ. Avvalo подскажет, на что обратить внимание и что делать дальше."
            ),
            "prompt": "Текст, ссылка или описание ситуации",
            "textarea_placeholder": (
                "Например: мне прислали скрин оплаты и просят отдать товар до "
                "зачисления денег..."
            ),
            "image_hint": "На изображении должны быть хорошо видны переписка, чек, QR-код или документ.",
            "use_cases": [
                "Сообщение или переписка",
                "Ссылка или QR-код",
                "Скрин оплаты или запрос на оплату",
                "Предложение о работе или сотрудничестве",
                "Документ или запрос",
            ],
            "trust": [
                "Проверяет ситуацию, а не человека",
                "Не выносит вердиктов, а подсказывает шаги проверки",
                "Даёт рекомендации, но не гарантирует результат",
                "Текст, изображения и ответ не сохраняются",
            ],
        },
    },
}
