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
        "hero_kicker": "Shubha tug‘ildimi?",
        "use_cases_label": "Avvalo'ga nimalarni yuborish mumkin",
        "composer_kicker": "Anonim tekshiruv",
        "composer_title": "Vaziyatni tasvirlab bering",
        "composer_body": (
            "Matn yoki havolani kiriting. Kerak bo‘lsa, skrinshot yoki rasm qo‘shing. "
            "Bu to‘lov so‘rovi, taklif, hujjat yoki yozishma bo‘lishi mumkin."
        ),
        "input_hint": "SMS kod, parol va karta ma’lumotlarini yashiring.",
        "outcome_title": "Javobda nimalar bo‘ladi",
        "outcome_body": (
            "Avvalo yakuniy hukm chiqarmaydi va rasmiy manbani tekshirganini da’vo qilmaydi. "
            "Javobda vaziyatni mustaqil tekshirish uchun aniq qadamlar bo‘ladi."
        ),
        "outcomes": [
            {
                "title": "Nimaga e’tibor berish kerak",
                "body": "Bosim, shoshiltirish va vaziyatdagi nomuvofiqliklar.",
            },
            {
                "title": "Hozir nima qilish kerak",
                "body": "Manbani mustaqil tekshirish uchun aniq qadamlar.",
            },
            {
                "title": "Nima noaniq qoladi",
                "body": "Tasdiqlanmagan ma’lumotlar va o‘tkazilmagan tashqi tekshiruvlar.",
            },
            {
                "title": "Qanday savollar berish kerak",
                "body": "Suhbatdoshga yoki rasmiy tashkilotga berish mumkin bo‘lgan qisqa savollar.",
            },
        ],
        "boundary_title": "Vaziyatni tekshiring, odamni emas",
        "boundary_body": (
            "Avvalo vaziyat, material, jarayon yoki manbadagi belgilarni tahlil qiladi. "
            "U odamning obro‘siga baho bermaydi, o‘tkazilmagan tashqi tekshiruvni "
            "o‘tkazilgandek ko‘rsatmaydi va yakuniy hukm chiqarmaydi."
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
        "submit": "Tekshirish",
        "checking": "Tekshirilmoqda...",
        "result_error_title": "Hozir tekshira olmadik",
        "empty_error": "Matn kiriting yoki matni aniq ko‘rinadigan rasm yuklang.",
        "too_long_error": "Matn juda uzun. Uni qisqartirib, qayta yuboring.",
        "consent_error": "Avval maxfiylik shartlariga rozilik bering.",
        "check": {
            "name": "Vaziyat tekshiruvi",
            "headline": "Vaziyatni Avvalo bilan tekshiring.",
            "subhead": (
                "Biror qaror qilishdan oldin nimaga e’tibor berish va vaziyatni "
                "qanday tekshirishni bilib oling."
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
        "hero_kicker": "Возникли сомнения?",
        "use_cases_label": "Что можно отправить в Avvalo",
        "composer_kicker": "Анонимная проверка",
        "composer_title": "Опишите ситуацию",
        "composer_body": (
            "Вставьте текст или ссылку. При необходимости добавьте скриншот или фото. "
            "Это может быть запрос на оплату, предложение, документ или переписка."
        ),
        "input_hint": "Скройте SMS-коды, пароли и полные данные карты.",
        "outcome_title": "Что будет в ответе",
        "outcome_body": (
            "Avvalo не выносит окончательных вердиктов и не утверждает, что проверил "
            "официальный источник. В ответе будут понятные шаги для самостоятельной проверки."
        ),
        "outcomes": [
            {
                "title": "На что обратить внимание",
                "body": "Давление, спешка и несостыковки в ситуации.",
            },
            {
                "title": "Что сделать сейчас",
                "body": "Конкретные шаги для самостоятельной проверки источника.",
            },
            {
                "title": "Что останется неизвестным",
                "body": "Неподтверждённые сведения и внешние проверки, которые не проводились.",
            },
            {
                "title": "Что спросить",
                "body": "Короткие вопросы собеседнику или официальной организации.",
            },
        ],
        "boundary_title": "Проверяйте ситуацию, а не человека",
        "boundary_body": (
            "Avvalo анализирует признаки в ситуации, материале, процессе или источнике. "
            "Он не оценивает репутацию человека, не заявляет о внешних проверках, "
            "которых не было, и не выносит окончательных вердиктов."
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
        "submit": "Проверить",
        "checking": "Проверяем...",
        "result_error_title": "Сейчас не удалось проверить",
        "empty_error": "Вставьте текст или загрузите изображение с читаемым текстом.",
        "too_long_error": "Текст получился слишком длинным. Сократите его и отправьте ещё раз.",
        "consent_error": "Сначала примите условия конфиденциальности.",
        "check": {
            "name": "Проверка ситуации",
            "headline": "Проверьте ситуацию с Avvalo.",
            "subhead": (
                "Перед тем как принять решение, узнайте, на что обратить внимание "
                "и как самостоятельно проверить ситуацию."
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
