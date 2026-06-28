"""FastAPI routes for the anonymous web channel."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.texts import DEFAULT_LANGUAGE, LANGUAGE_LABELS, LANGUAGES, t
from app.config import Settings, get_settings
from app.data import repo
from app.engine import CheckInput, InputType, Language, run_check
from app.engine.faces import FACES
from app.privacy.consent import is_consent_current
from app.web.abuse import read_limited_upload, require_turnstile_for_image
from app.web.session import get_or_create_web_session, set_web_session_cookie

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).with_name("templates")))
DEV_WEB_SESSION_SECRET = "development-web-session-secret"

WEB_COPY = {
    "uz_latn": {
        "html_lang": "uz-Latn",
        "nav_family": "Oila himoyasi",
        "nav_seller": "Sotuvchi himoyasi",
        "privacy_link": "Maxfiylik",
        "language_label": "Til",
        "title": "Avvalo",
        "privacy_title": "Maxfiylik",
        "consent_label": "Maxfiylik shartlariga roziman",
        "message_label": "Xabar matni",
        "caption_label": "Qo'shimcha izoh",
        "image_label": "Skrinshot yoki rasm",
        "submit": "Tekshirish",
        "result_error_title": "Tekshiruv amalga oshmadi",
        "result_empty": "Javob matni yo'q.",
        "meta_status": "Holat",
        "meta_latency": "Vaqt",
        "meta_cost": "Narx",
        "empty_error": "Matn kiriting yoki o'qilishi mumkin bo'lgan rasm yuklang.",
        "consent_error": "Avval maxfiylik shartlariga rozilik bering.",
        "unknown_face_error": "Noma'lum tekshiruv turi.",
        "faces": {
            "family_shield": {
                "eyebrow": "Oilalar uchun",
                "name": "Oila himoyasi",
                "headline": "Shubhali xabarni yuboring, keyin harakat qiling.",
                "subhead": (
                    "Avvalo xabar yoki skrinshotdagi ogohlantiruvchi belgilarni ko'rsatadi: "
                    "nimani tekshirish va qanday savol berish kerak."
                ),
                "prompt": "Bank, qarindosh, yetkazib berish, ish yoki oldindan to'lov haqidagi xabarni joylang.",
                "textarea_placeholder": "Masalan: SMS kodni yuboring, hisob bloklanadi...",
                "caption_placeholder": "Agar kerak bo'lsa, qisqa kontekst qo'shing",
                "image_hint": "Matn ko'rinadigan bitta rasm. OCR uchun Turnstile talab qilinadi.",
                "trust": [
                    "Vaziyat tekshiriladi, odam emas",
                    "Xavfsiz yoki firibgar degan hukm berilmaydi",
                    "Yuborilgan matn saqlanmaydi",
                ],
            },
            "seller_guard": {
                "eyebrow": "Sotuvchilar uchun",
                "name": "Sotuvchi himoyasi",
                "headline": "Tovarni berishdan oldin xaridor yuborgan dalilni tekshiring.",
                "subhead": (
                    "To'lov skrinshoti, kuryer bosimi yoki qaytarim so'rovini mustaqil tekshiruv "
                    "ro'yxatiga aylantiradi."
                ),
                "prompt": "Xaridor yuborgan chek, buyurtma suhbati yoki yetkazish so'rovini joylang.",
                "textarea_placeholder": "Masalan: pul o'tkazdim, kuryer kutyapti, skrinshot mana...",
                "caption_placeholder": "Buyurtma summasi yoki muhim kontekst",
                "image_hint": "Chek rasmi dalil emas; javob bank ilovasida nimani tekshirishni aytadi.",
                "trust": [
                    "Pul kelganini skrinshotdan tasdiqlamaydi",
                    "Bank ilovasida mustaqil tekshirishni talab qiladi",
                    "Tovarni berishdan oldin xavf belgilarini ko'rsatadi",
                ],
            },
        },
    },
    "uz_cyrl": {
        "html_lang": "uz-Cyrl",
        "nav_family": "Оила ҳимояси",
        "nav_seller": "Сотувчи ҳимояси",
        "privacy_link": "Махфийлик",
        "language_label": "Тил",
        "title": "Avvalo",
        "privacy_title": "Махфийлик",
        "consent_label": "Махфийлик шартларига розиман",
        "message_label": "Хабар матни",
        "caption_label": "Қўшимча изоҳ",
        "image_label": "Скриншот ёки расм",
        "submit": "Текшириш",
        "result_error_title": "Текширув амалга ошмади",
        "result_empty": "Жавоб матни йўқ.",
        "meta_status": "Ҳолат",
        "meta_latency": "Вақт",
        "meta_cost": "Нарх",
        "empty_error": "Матн киритинг ёки ўқилиши мумкин бўлган расм юкланг.",
        "consent_error": "Аввал махфийлик шартларига розилик беринг.",
        "unknown_face_error": "Номаълум текширув тури.",
        "faces": {
            "family_shield": {
                "eyebrow": "Оилалар учун",
                "name": "Оила ҳимояси",
                "headline": "Шубҳали хабарни юборинг, кейин ҳаракат қилинг.",
                "subhead": (
                    "Avvalo хабар ёки скриншотдаги огоҳлантирувчи белгиларни кўрсатади: "
                    "нимани текшириш ва қандай савол бериш керак."
                ),
                "prompt": "Банк, қариндош, етказиб бериш, иш ёки олдиндан тўлов ҳақидаги хабарни жойланг.",
                "textarea_placeholder": "Масалан: SMS кодни юборинг, ҳисоб блокланади...",
                "caption_placeholder": "Агар керак бўлса, қисқа контекст қўшинг",
                "image_hint": "Матн кўринадиган битта расм. OCR учун Turnstile талаб қилинади.",
                "trust": [
                    "Вазият текширилади, одам эмас",
                    "Хавфсиз ёки фирибгар деган ҳукм берилмайди",
                    "Юборилган матн сақланмайди",
                ],
            },
            "seller_guard": {
                "eyebrow": "Сотувчилар учун",
                "name": "Сотувчи ҳимояси",
                "headline": "Товарни беришдан олдин харидор юборган далилни текширинг.",
                "subhead": (
                    "Тўлов скриншоти, курьер босими ёки қайтарим сўровини мустақил текширув "
                    "рўйхатига айлантиради."
                ),
                "prompt": "Харидор юборган чек, буюртма суҳбати ёки етказиш сўровини жойланг.",
                "textarea_placeholder": "Масалан: пул ўтказдим, курьер кутяпти, скриншот мана...",
                "caption_placeholder": "Буюртма суммаси ёки муҳим контекст",
                "image_hint": "Чек расми далил эмас; жавоб банк иловасида нимани текширишни айтади.",
                "trust": [
                    "Пул келганини скриншотдан тасдиқламайди",
                    "Банк иловасида мустақил текширишни талаб қилади",
                    "Товарни беришдан олдин хавф белгиларини кўрсатади",
                ],
            },
        },
    },
    "ru": {
        "html_lang": "ru",
        "nav_family": "Защита семьи",
        "nav_seller": "Защита продавца",
        "privacy_link": "Конфиденциальность",
        "language_label": "Язык",
        "title": "Avvalo",
        "privacy_title": "Конфиденциальность",
        "consent_label": "Я согласен с условиями конфиденциальности",
        "message_label": "Текст сообщения",
        "caption_label": "Короткий контекст",
        "image_label": "Скриншот или фото",
        "submit": "Проверить",
        "result_error_title": "Не удалось проверить",
        "result_empty": "Нет текста ответа.",
        "meta_status": "Статус",
        "meta_latency": "Время",
        "meta_cost": "Стоимость",
        "empty_error": "Вставьте текст или загрузите читаемое изображение.",
        "consent_error": "Сначала примите условия конфиденциальности.",
        "unknown_face_error": "Неизвестный тип проверки.",
        "faces": {
            "family_shield": {
                "eyebrow": "Для семей",
                "name": "Защита семьи",
                "headline": "Проверьте сомнительное сообщение до ответа или оплаты.",
                "subhead": (
                    "Avvalo показывает тревожные признаки в сообщении или скриншоте: "
                    "что проверить и какие вопросы задать."
                ),
                "prompt": "Вставьте сообщение от банка, родственника, доставки, работодателя или продавца.",
                "textarea_placeholder": "Например: пришлите SMS-код, иначе счёт будет заблокирован...",
                "caption_placeholder": "Добавьте короткий контекст, если он важен",
                "image_hint": "Одно изображение с читаемым текстом. Для OCR нужен Turnstile.",
                "trust": [
                    "Проверяется ситуация, а не человек",
                    "Нет вердиктов безопасно или мошенник",
                    "Отправленный текст не сохраняется",
                ],
            },
            "seller_guard": {
                "eyebrow": "Для продавцов",
                "name": "Защита продавца",
                "headline": "Проверьте доказательство от покупателя до передачи товара.",
                "subhead": (
                    "Платёжный скриншот, давление курьером или запрос на возврат превращаются "
                    "в список независимых проверок."
                ),
                "prompt": "Вставьте чек, переписку по заказу или запрос на доставку от покупателя.",
                "textarea_placeholder": "Например: перевёл деньги, курьер ждёт, вот скриншот...",
                "caption_placeholder": "Сумма заказа или важный контекст",
                "image_hint": "Скриншот чека не доказывает оплату; ответ подскажет, что проверить в банке.",
                "trust": [
                    "Не подтверждает приход денег по скриншоту",
                    "Требует самостоятельной проверки в банковском приложении",
                    "Показывает признаки риска до передачи товара",
                ],
            },
        },
    },
}

FACE_PATHS = {
    "family_shield": "/family-shield",
    "seller_guard": "/seller-guard",
}


@router.get("/healthz")
async def healthz() -> dict[str, bool]:
    """Health check for local deploys and smoke tests."""

    return {"ok": True}


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, language: str = DEFAULT_LANGUAGE) -> HTMLResponse:
    """Render the default Family Shield check page."""

    return _face_page(request, face="family_shield", language=language)


@router.get("/family-shield", response_class=HTMLResponse)
async def family_shield(request: Request, language: str = DEFAULT_LANGUAGE) -> HTMLResponse:
    """Render the Family Shield check page."""

    return _face_page(request, face="family_shield", language=language)


@router.get("/seller-guard", response_class=HTMLResponse)
async def seller_guard(request: Request, language: str = DEFAULT_LANGUAGE) -> HTMLResponse:
    """Render the Seller Guard check page."""

    return _face_page(request, face="seller_guard", language=language)


def _face_page(request: Request, *, face: str, language: str) -> HTMLResponse:
    """Render one focused check surface for one face."""

    language = _normalize_language(language)
    settings = _settings_or_none(request)
    web_session = get_or_create_web_session(request, secret=_web_secret(settings))
    copy = WEB_COPY[language]
    response = templates.TemplateResponse(
        request,
        "index.html",
        {
            "copy": copy,
            "face": face,
            "face_copy": copy["faces"][face],
            "face_path": FACE_PATHS[face],
            "other_face": "seller_guard" if face == "family_shield" else "family_shield",
            "other_face_path": FACE_PATHS[
                "seller_guard" if face == "family_shield" else "family_shield"
            ],
            "languages": LANGUAGES,
            "language_labels": LANGUAGE_LABELS,
            "language": language,
            "privacy_text": t("privacy_notice", language),
            "turnstile_site_key": (
                settings.turnstile_site_key.get_secret_value()
                if settings and settings.turnstile_site_key
                else None
            ),
        },
    )
    set_web_session_cookie(response, web_session, secure=_cookie_secure(settings))
    return response


@router.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request, language: str = DEFAULT_LANGUAGE) -> HTMLResponse:
    """Render the localized privacy notice."""

    language = _normalize_language(language)
    copy = WEB_COPY[language]
    return templates.TemplateResponse(
        request,
        "privacy.html",
        {
            "copy": copy,
            "language": language,
            "languages": LANGUAGES,
            "language_labels": LANGUAGE_LABELS,
            "privacy_text": t("privacy", language),
        },
    )


@router.post("/check", response_class=HTMLResponse)
async def check(
    request: Request,
    face: Annotated[str, Form()] = "family_shield",
    language: Annotated[str, Form()] = DEFAULT_LANGUAGE,
    text: Annotated[str, Form()] = "",
    caption: Annotated[str, Form()] = "",
    consent: Annotated[str | None, Form()] = None,
    turnstile_token: Annotated[str | None, Form(alias="cf-turnstile-response")] = None,
    image: Annotated[UploadFile | None, File()] = None,
) -> HTMLResponse:
    """Build a CheckInput and call the shared engine pipeline."""

    settings = _settings_or_error(request)
    language = _normalize_language(language)
    copy = WEB_COPY[language]
    if face not in FACES:
        raise HTTPException(status_code=400, detail=copy["unknown_face_error"])

    web_session = get_or_create_web_session(request, secret=_web_secret(settings))
    session_factory = _session_factory_or_none(request)
    image_bytes = await read_limited_upload(image)
    await require_turnstile_for_image(
        image_bytes=image_bytes,
        token=turnstile_token,
        request=request,
        settings=settings,
    )

    if not text.strip() and not image_bytes:
        return _partial(
            request,
            status_code=400,
            error=copy["empty_error"],
            copy=copy,
            web_session=web_session,
        )

    input_type = InputType.image if image_bytes else InputType.text
    check_input = CheckInput(
        face=face,
        user_key=web_session.user_key,
        language=Language(language),
        input_type=input_type,
        raw_text=text if input_type is InputType.text else None,
        image_bytes=image_bytes,
        caption=caption or None,
    )

    if session_factory is None:
        if consent != "yes":
            return _partial(
                request,
                status_code=400,
                error=copy["consent_error"],
                copy=copy,
                web_session=web_session,
            )
        result = await run_check(
            check_input,
            settings=settings,
            rate_limit_override=settings.web_daily_limit,
        )
        return _partial(request, result=result, copy=copy, web_session=web_session)

    async with session_factory() as session:
        if not await _ensure_web_consent(
            session,
            user_key=web_session.user_key,
            face=face,
            language=language,
            settings=settings,
            accepted=consent == "yes",
        ):
            return _partial(
                request,
                status_code=400,
                error=copy["consent_error"],
                copy=copy,
                web_session=web_session,
            )

        result = await run_check(
            check_input,
            session=session,
            settings=settings,
            rate_limit_override=settings.web_daily_limit,
        )
        await session.commit()

    return _partial(request, result=result, copy=copy, web_session=web_session)


async def _ensure_web_consent(
    session: AsyncSession,
    *,
    user_key: str,
    face: str,
    language: str,
    settings: Settings,
    accepted: bool,
) -> bool:
    consent = await repo.get_consent(session, user_key=user_key, face=face)
    if is_consent_current(consent, settings.notice_version):
        return True
    if not accepted:
        return False
    await repo.upsert_consent(
        session,
        user_key=user_key,
        face=face,
        notice_version=settings.notice_version,
        language=language,
    )
    return True


def _partial(
    request: Request,
    *,
    result=None,
    error: str | None = None,
    copy: dict | None = None,
    status_code: int = 200,
    web_session=None,
) -> HTMLResponse:
    language = result.language.value if result is not None else DEFAULT_LANGUAGE
    copy = copy or WEB_COPY[language]
    response = templates.TemplateResponse(
        request,
        "_result.html",
        {"copy": copy, "result": result, "error": error},
        status_code=status_code,
    )
    if web_session is not None:
        set_web_session_cookie(
            response, web_session, secure=_cookie_secure(_settings_or_none(request))
        )
    return response


def _cookie_secure(settings: Settings | None) -> bool:
    return bool(settings.web_cookie_secure) if settings is not None else False


def _settings_or_none(request: Request) -> Settings | None:
    return getattr(request.app.state, "settings", None)


def _settings_or_error(request: Request) -> Settings:
    settings = _settings_or_none(request)
    if settings is not None:
        return settings
    try:
        return get_settings()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Web app is not configured.") from exc


def _session_factory_or_none(request: Request) -> async_sessionmaker[AsyncSession] | None:
    return getattr(request.app.state, "session_factory", None)


def _web_secret(settings: Settings | None) -> str:
    if settings is None:
        return DEV_WEB_SESSION_SECRET
    return settings.web_session_secret.get_secret_value()


def _normalize_language(language: str) -> str:
    return language if language in LANGUAGES else DEFAULT_LANGUAGE
