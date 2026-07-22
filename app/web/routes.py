"""FastAPI routes for the anonymous web channel."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.texts import DEFAULT_LANGUAGE, LANGUAGE_LABELS, LANGUAGES, t
from app.config import Settings, get_settings
from app.content import list_published_posts
from app.data import repo
from app.engine import (
    BILLABLE_STATUSES,
    CheckInput,
    CheckResult,
    CheckStatus,
    InputType,
    Language,
    run_check,
)
from app.engine.format import format_status_message
from app.privacy.consent import is_consent_current
from app.web.abuse import (
    pseudonymous_ip_key,
    read_limited_upload,
    require_same_origin,
    require_turnstile_for_image,
)
from app.web.editorial_copy import EDITORIAL_COPY
from app.web.session import get_or_create_web_session, set_web_session_cookie

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).with_name("templates")))


def _static_version() -> str:
    """Fingerprint browser-cached assets so each deploy gets fresh URLs."""

    static_dir = Path(__file__).with_name("static")
    digest = sha256()
    for name in (
        "styles.css",
        "check.js",
        "admin.js",
        "favicon.ico",
        "apple-touch-icon.png",
        "icon-192.png",
        "icon-512.png",
    ):
        path = static_dir / name
        digest.update(name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


templates.env.globals["static_version"] = _static_version()
DEV_WEB_SESSION_SECRET = "development-web-session-secret"
WEB_MAX_TEXT_CHARS = 6000
WEB_MAX_CAPTION_CHARS = 500
WEB_IP_FACE_PREFIX = "web_ip:"

# The form's own maxlength attributes come from the same constants the POST
# handler validates against, so the browser can never invite an oversized body.
templates.env.globals["max_text_chars"] = WEB_MAX_TEXT_CHARS
templates.env.globals["max_caption_chars"] = WEB_MAX_CAPTION_CHARS
templates.env.globals["short_language_labels"] = {
    "uz_latn": "O‘z",
    "uz_cyrl": "Ўз",
    "ru": "RU",
}
# The per-IP web limit refunds exactly the statuses the engine's per-user
# limit refunds — one shared definition so the two can't drift.
WEB_BILLABLE_STATUSES = BILLABLE_STATUSES

WEB_COPY = {
    "uz_latn": {
        "html_lang": "uz-Latn",
        "privacy_link": "Maxfiylik",
        "language_label": "Til",
        "nav_label": "Asosiy bo‘limlar",
        "nav_check": "Tekshiruv",
        "nav_cases": "Holatlar",
        "trust_label": "Ishonch",
        "skip_to_check": "Tekshiruvga o'tish",
        "brand_tagline": "Harakatdan oldin tekshiring",
        "hero_kicker": "Shubha tug‘ildimi?",
        "use_cases_label": "Avvalo'ga nimalarni yuborish mumkin",
        "composer_kicker": "Anonim tekshiruv",
        "composer_title": "Vaziyatni Avvalo'ga yuboring",
        "composer_body": (
            "Matn yoki havolani kiriting. Skrinshot, to‘lov cheki yoki hujjat "
            "rasmini ham qo‘shishingiz mumkin."
        ),
        "input_hint": "SMS kod, parol va karta ma’lumotlarini yashiring.",
        "outcome_title": "Javobda nima bo‘ladi",
        "outcome_body": "Qaror o‘rniga — tushunarli va xavfsiz harakat rejasi.",
        "outcomes": [
            {
                "title": "Nima e’tibor talab qiladi",
                "body": "Bosim, shoshiltirish va vaziyatdagi nomuvofiqliklar.",
            },
            {
                "title": "Nimani tekshirish kerak",
                "body": "Manbani mustaqil tasdiqlash uchun aniq qadamlar.",
            },
            {
                "title": "Hozir nima qilish kerak",
                "body": "Xavfsiz keyingi harakat va beriladigan savollar.",
            },
        ],
        "boundary_title": "Avvalo odamga baho bermaydi",
        "boundary_body": (
            "Biz vaziyatdagi belgilarni tahlil qilamiz, odamni tekshirmaymiz va "
            "yakuniy hukm chiqarmaymiz."
        ),
        "footer_note": "Shoshilmang. Avval tekshiring, keyin harakat qiling.",
        "result_ready": "Tahlil tayyor",
        "result_title": "Tekshiruv rejangiz",
        "title": "Avvalo",
        "privacy_title": "Maxfiylik",
        "consent_label": "Maxfiylik shartlarini o'qidim va roziman",
        "caption_label": "Qo'shimcha izoh",
        "image_label": "Skrinshot yoki rasm",
        "optional_label": "ixtiyoriy",
        "choose_file": "Rasm tanlash",
        "clear_file": "Faylni olib tashlash",
        "submit": "Tekshirish",
        "checking": "Tekshirilmoqda...",
        "result_error_title": "Hozir tekshirib bo'lmadi",
        "empty_error": "Tekshirish uchun xabar yozing yoki matni ko'rinadigan rasm yuklang.",
        "too_long_error": "Matn biroz uzun. Qisqartirib, qayta yuboring.",
        "consent_error": "Avval maxfiylik shartlariga rozilik bering.",
        "faces": {
            "family": {
                "name": "Vaziyat tekshiruvi",
                "headline": (
                    "Javob berishdan, pul to‘lashdan yoki ma’lumot yuborishdan "
                    "oldin tekshiring."
                ),
                "subhead": (
                    "Avvalo xavf belgilarini ajratadi va nimani mustaqil tekshirish, "
                    "hozir nima qilish va qanday savol berishni ko‘rsatadi."
                ),
                "prompt": "Matn, havola yoki vaziyat tavsifi",
                "textarea_placeholder": (
                    "Masalan: to‘lov skrinshotini yuborib, pul tushmasidan oldin "
                    "tovarni berishimni so‘rashyapti..."
                ),
                "caption_placeholder": "Kerak bo'lsa: kim yubordi, nima so'rayapti?",
                "image_hint": "Yozishma, chek, QR-kod yoki hujjat aniq ko‘rinsin.",
                "use_cases": [
                    "Bank yoki SMS xabari",
                    "Havola yoki QR-kod",
                    "To‘lov skrinshoti",
                    "Ish yoki savdo taklifi",
                    "Hujjat yoki so‘rov",
                ],
                "trust": [
                    "Odamni emas, vaziyatni tekshiradi",
                    "Hukm emas, aniq tekshiruv qadamlari",
                    "Matn va rasm tekshiruv tarixida saqlanmaydi",
                ],
            },
        },
    },
    "uz_cyrl": {
        "html_lang": "uz-Cyrl",
        "privacy_link": "Махфийлик",
        "language_label": "Тил",
        "nav_label": "Асосий бўлимлар",
        "nav_check": "Текширув",
        "nav_cases": "Ҳолатлар",
        "trust_label": "Ишонч",
        "skip_to_check": "Текширувга ўтиш",
        "brand_tagline": "Ҳаракатдан олдин текширинг",
        "hero_kicker": "Шубҳа туғилдими?",
        "use_cases_label": "Avvalo'га нималарни юбориш мумкин",
        "composer_kicker": "Аноним текширув",
        "composer_title": "Вазиятни Avvalo'га юборинг",
        "composer_body": (
            "Матн ёки ҳаволани киритинг. Скриншот, тўлов чеки ёки ҳужжат "
            "расмини ҳам қўшишингиз мумкин."
        ),
        "input_hint": "SMS-код, пароль ва карта маълумотларини яширинг.",
        "outcome_title": "Жавобда нима бўлади",
        "outcome_body": "Қарор ўрнига — тушунарли ва хавфсиз ҳаракат режаси.",
        "outcomes": [
            {
                "title": "Нима эътибор талаб қилади",
                "body": "Босим, шошилтириш ва вазиятдаги номувофиқликлар.",
            },
            {
                "title": "Нимани текшириш керак",
                "body": "Манбани мустақил тасдиқлаш учун аниқ қадамлар.",
            },
            {
                "title": "Ҳозир нима қилиш керак",
                "body": "Хавфсиз кейинги ҳаракат ва бериладиган саволлар.",
            },
        ],
        "boundary_title": "Avvalo одамга баҳо бермайди",
        "boundary_body": (
            "Биз вазиятдаги белгиларни таҳлил қиламиз, одамни текширмаймиз ва "
            "якуний ҳукм чиқармаймиз."
        ),
        "footer_note": "Шошилманг. Аввал текширинг, кейин ҳаракат қилинг.",
        "result_ready": "Таҳлил тайёр",
        "result_title": "Текширув режангиз",
        "title": "Avvalo",
        "privacy_title": "Махфийлик",
        "consent_label": "Махфийлик шартларини ўқидим ва розиман",
        "caption_label": "Қўшимча изоҳ",
        "image_label": "Скриншот ёки расм",
        "optional_label": "ихтиёрий",
        "choose_file": "Расм танлаш",
        "clear_file": "Файлни олиб ташлаш",
        "submit": "Текшириш",
        "checking": "Текширилмоқда...",
        "result_error_title": "Ҳозир текшириб бўлмади",
        "empty_error": "Текшириш учун хабар ёзинг ёки матни кўринадиган расм юкланг.",
        "too_long_error": "Матн бироз узун. Қисқартириб, қайта юборинг.",
        "consent_error": "Аввал махфийлик шартларига розилик беринг.",
        "faces": {
            "family": {
                "name": "Вазият текшируви",
                "headline": (
                    "Жавоб беришдан, пул тўлашдан ёки маълумот юборишдан олдин "
                    "текширинг."
                ),
                "subhead": (
                    "Avvalo хавф белгиларини ажратади ва нимани мустақил текшириш, "
                    "ҳозир нима қилиш ва қандай савол беришни кўрсатади."
                ),
                "prompt": "Матн, ҳавола ёки вазият тавсифи",
                "textarea_placeholder": (
                    "Масалан: тўлов скриншотини юбориб, пул тушмасидан олдин "
                    "товарни беришимни сўрашяпти..."
                ),
                "caption_placeholder": "Керак бўлса: ким юборди, нима сўраяпти?",
                "image_hint": "Ёзишма, чек, QR-код ёки ҳужжат аниқ кўринсин.",
                "use_cases": [
                    "Банк ёки SMS хабари",
                    "Ҳавола ёки QR-код",
                    "Тўлов скриншоти",
                    "Иш ёки савдо таклифи",
                    "Ҳужжат ёки сўров",
                ],
                "trust": [
                    "Одамни эмас, вазиятни текширади",
                    "Ҳукм эмас, аниқ текширув қадамлари",
                    "Матн ва расм текширув тарихида сақланмайди",
                ],
            },
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
        "brand_tagline": "Проверяйте до действия",
        "hero_kicker": "Возникли сомнения?",
        "use_cases_label": "Что можно отправить в Avvalo",
        "composer_kicker": "Анонимная проверка",
        "composer_title": "Отправьте ситуацию в Avvalo",
        "composer_body": (
            "Вставьте текст или ссылку. Можно также добавить скриншот, чек оплаты "
            "или фото документа."
        ),
        "input_hint": "Скройте SMS-коды, пароли и полные данные карты.",
        "outcome_title": "Что будет в ответе",
        "outcome_body": "Не вердикт, а понятный и безопасный план действий.",
        "outcomes": [
            {
                "title": "Что требует внимания",
                "body": "Давление, спешка и несостыковки в ситуации.",
            },
            {
                "title": "Что проверить",
                "body": "Конкретные шаги для независимого подтверждения.",
            },
            {
                "title": "Что сделать сейчас",
                "body": "Безопасное следующее действие и вопросы собеседнику.",
            },
        ],
        "boundary_title": "Avvalo не оценивает людей",
        "boundary_body": (
            "Мы разбираем признаки в ситуации, не проверяем личность и не выносим "
            "окончательный вердикт."
        ),
        "footer_note": "Не спешите. Сначала проверьте, потом действуйте.",
        "result_ready": "Разбор готов",
        "result_title": "Ваш план проверки",
        "title": "Avvalo",
        "privacy_title": "Конфиденциальность",
        "consent_label": "Я прочитал условия конфиденциальности и согласен",
        "caption_label": "Короткий контекст",
        "image_label": "Скриншот или фото",
        "optional_label": "необязательно",
        "choose_file": "Выбрать фото",
        "clear_file": "Убрать файл",
        "submit": "Проверить",
        "checking": "Проверяем...",
        "result_error_title": "Сейчас проверить не получилось",
        "empty_error": "Вставьте текст или загрузите читаемое изображение.",
        "too_long_error": "Текст получился слишком длинным. Сократите его и отправьте ещё раз.",
        "consent_error": "Сначала примите условия конфиденциальности.",
        "faces": {
            "family": {
                "name": "Проверка ситуации",
                "headline": (
                    "Проверьте до того, как ответить, заплатить или поделиться данными."
                ),
                "subhead": (
                    "Avvalo выделит тревожные признаки и подскажет, что проверить "
                    "самостоятельно, что сделать сейчас и что спросить."
                ),
                "prompt": "Текст, ссылка или описание ситуации",
                "textarea_placeholder": (
                    "Например: прислали скрин оплаты и просят отдать товар до "
                    "зачисления денег..."
                ),
                "caption_placeholder": "Если нужно: кто написал и чего просит?",
                "image_hint": "Подойдёт читаемый скриншот переписки, чека, QR-кода или документа.",
                "use_cases": [
                    "Сообщение от банка",
                    "Ссылка или QR-код",
                    "Скрин оплаты",
                    "Работа или сделка",
                    "Документ или запрос",
                ],
                "trust": [
                    "Проверяем ситуацию, а не человека",
                    "Конкретные шаги проверки вместо вердикта",
                    "Текст и изображения не сохраняются в истории",
                ],
            },
        },
    },
}

@router.get("/healthz")
async def healthz() -> dict[str, bool]:
    """Process liveness check for external monitoring."""

    return {"ok": True}


@router.get("/readyz", response_model=None)
async def readyz(request: Request) -> Response:
    """Deployment readiness check that also verifies the database connection."""

    session_factory = _session_factory_or_none(request)
    if session_factory is None:
        return Response(status_code=503)
    try:
        async with session_factory() as session:
            await session.execute(sql_text("SELECT 1"))
    except Exception:
        return Response(status_code=503)
    return JSONResponse({"ok": True})


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, language: str = DEFAULT_LANGUAGE) -> HTMLResponse:
    """Render the home page: the consumer check form above how-it-works.

    The form posts to the same POST /check handler as the standalone page, so
    landing here costs a visitor no extra click. Unlike ``_check_page`` this
    deliberately does *not* mint a session cookie — nothing on a GET needs one,
    and POST /check creates it on first submit anyway.
    """

    language = _normalize_language(language)
    copy = WEB_COPY[language]
    latest_posts = await _latest_editorial_posts(request, language=language)
    return _no_store(templates.TemplateResponse(
        request,
            "checker.html",
        {
            "copy": copy,
            "face_copy": copy["faces"]["family"],
            "language_path": "/",
            "languages": LANGUAGES,
            "language_labels": LANGUAGE_LABELS,
            "language": language,
            "privacy_text": t("privacy_notice", language),
            "turnstile_site_key": _turnstile_site_key(_settings_or_none(request)),
            "editorial": EDITORIAL_COPY[language],
            "latest_posts": latest_posts,
        },
    ))


@router.get("/check", response_class=HTMLResponse)
async def family_check(request: Request, language: str = DEFAULT_LANGUAGE) -> HTMLResponse:
    """Render the consumer checker and its result surface."""

    return await _check_page(request, language=language)


@router.get("/merchants", include_in_schema=False)
async def retired_merchants(language: str = DEFAULT_LANGUAGE) -> RedirectResponse:
    """Preserve old bookmarks while sending users to the unified checker."""

    response = RedirectResponse(
        url=f"/check?language={_normalize_language(language)}",
        status_code=308,
    )
    response.headers["Cache-Control"] = "no-store"
    return response


async def _check_page(request: Request, *, language: str) -> HTMLResponse:
    """Render the unified consumer check surface."""

    language = _normalize_language(language)
    settings = _settings_or_none(request)
    web_session = get_or_create_web_session(request, secret=_web_secret(settings))
    copy = WEB_COPY[language]
    latest_posts = await _latest_editorial_posts(request, language=language)
    response = templates.TemplateResponse(
        request,
            "checker.html",
        {
            "copy": copy,
            "face_copy": copy["faces"]["family"],
            "language_path": "/check",
            "languages": LANGUAGES,
            "language_labels": LANGUAGE_LABELS,
            "language": language,
            "privacy_text": t("privacy_notice", language),
            "turnstile_site_key": _turnstile_site_key(settings),
            "editorial": EDITORIAL_COPY[language],
            "latest_posts": latest_posts,
        },
    )
    set_web_session_cookie(response, web_session, secure=_cookie_secure(request, settings))
    return _no_store(response)


def _turnstile_site_key(settings: Settings | None) -> str | None:
    if settings is None or not settings.turnstile_site_key:
        return None
    return settings.turnstile_site_key.get_secret_value()


@router.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request, language: str = DEFAULT_LANGUAGE) -> HTMLResponse:
    """Render the localized privacy notice."""

    language = _normalize_language(language)
    copy = WEB_COPY[language]
    return _no_store(templates.TemplateResponse(
        request,
        "privacy.html",
        {
            "copy": copy,
            "language": language,
            "languages": LANGUAGES,
            "language_labels": LANGUAGE_LABELS,
            "language_path": "/privacy",
            "privacy_text": t("privacy", language),
        },
    ))


@router.post("/check", response_class=HTMLResponse)
async def check(
    request: Request,
    language: Annotated[str, Form()] = DEFAULT_LANGUAGE,
    text: Annotated[str, Form()] = "",
    caption: Annotated[str, Form()] = "",
    consent: Annotated[str | None, Form()] = None,
    turnstile_token: Annotated[str | None, Form(alias="cf-turnstile-response")] = None,
    image: Annotated[UploadFile | None, File()] = None,
) -> HTMLResponse:
    """Build a CheckInput and call the shared engine pipeline."""

    require_same_origin(request)
    settings = _settings_or_error(request)
    language = _normalize_language(language)
    copy = WEB_COPY[language]
    face = "family"

    web_session = get_or_create_web_session(request, secret=_web_secret(settings))
    session_factory = _session_factory_or_none(request)
    if session_factory is None:
        raise HTTPException(status_code=503, detail="Web checks require database wiring.")

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

        limit_error = _form_limit_error(copy, text=text, caption=caption)
        if limit_error is not None:
            return _partial(
                request,
                status_code=413,
                error=limit_error,
                copy=copy,
                web_session=web_session,
            )

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
            raw_text=text or None,
            image_bytes=image_bytes,
            caption=caption or None,
        )

        ip_limit = await _reserve_web_ip_limit(
            session,
            request=request,
            settings=settings,
            face=face,
            language=Language(language),
            input_type=input_type,
        )
        if isinstance(ip_limit, CheckResult):
            return _partial(
                request,
                result=ip_limit,
                copy=copy,
                status_code=429,
                web_session=web_session,
            )

        try:
            result = await run_check(
                check_input,
                session=session,
                settings=settings,
                rate_limit_override=settings.web_daily_limit,
                commit_rate_limit_reservation=True,
            )
        except Exception:
            if isinstance(ip_limit, str):
                await repo.refund_usage(session, user_key=ip_limit, face=_web_ip_face(face))
                await session.commit()
            raise
        if isinstance(ip_limit, str) and result.status not in WEB_BILLABLE_STATUSES:
            await repo.refund_usage(session, user_key=ip_limit, face=_web_ip_face(face))
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


def _form_limit_error(copy: dict, *, text: str, caption: str) -> str | None:
    if len(text) > WEB_MAX_TEXT_CHARS or len(caption) > WEB_MAX_CAPTION_CHARS:
        return copy["too_long_error"]
    return None


async def _reserve_web_ip_limit(
    session: AsyncSession,
    *,
    request: Request,
    settings: Settings,
    face: str,
    language: Language,
    input_type: InputType,
) -> str | CheckResult | None:
    ip_key = pseudonymous_ip_key(request, secret=_web_secret(settings))
    if ip_key is None:
        return None

    ip_face = _web_ip_face(face)
    count = await repo.increment_usage(session, user_key=ip_key, face=ip_face)
    if count <= settings.web_daily_limit:
        return ip_key

    await repo.refund_usage(session, user_key=ip_key, face=ip_face)
    return CheckResult(
        status=CheckStatus.rate_limited,
        text=format_status_message(CheckStatus.rate_limited, language),
        language=language,
        input_type=input_type,
        error_class="WebIpDailyLimitExceeded",
    )


def _web_ip_face(face: str) -> str:
    return f"{WEB_IP_FACE_PREFIX}{face}"


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
            response,
            web_session,
            secure=_cookie_secure(request, _settings_or_none(request)),
        )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response


def _cookie_secure(request: Request, settings: Settings | None) -> bool:
    if settings is not None and settings.web_cookie_secure:
        return True
    forwarded = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip()
    return request.url.scheme.casefold() == "https" or forwarded.casefold() == "https"


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


async def _latest_editorial_posts(request: Request, *, language: str) -> list:
    """Return a small homepage preview without making content storage mandatory."""

    session_factory = _session_factory_or_none(request)
    if session_factory is None:
        return []
    async with session_factory() as session:
        return await list_published_posts(session, language=language, limit=3)


def _web_secret(settings: Settings | None) -> str:
    if settings is None:
        return DEV_WEB_SESSION_SECRET
    return settings.web_session_secret.get_secret_value()


def _normalize_language(language: str) -> str:
    return language if language in LANGUAGES else DEFAULT_LANGUAGE


def _no_store(response: HTMLResponse) -> HTMLResponse:
    """Keep an app page out of every cache.

    Without this these responses carry no ``Cache-Control`` and no validator, so
    browsers fall back to heuristic caching and happily reuse a stored copy —
    a returning visitor keeps seeing the previous deploy, and the stale HTML
    also pins them to the previous ``?v=`` asset URLs. ``no-store`` (rather than
    ``no-cache``) additionally stops shared proxies retaining a body that may
    carry a session ``Set-Cookie``.

    Static assets are unaffected: nginx caches ``/static/`` for a day and the
    fingerprinted query busts it on each deploy.
    """

    response.headers["Cache-Control"] = "no-store"
    return response
