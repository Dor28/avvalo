"""FastAPI routes for the anonymous web channel."""

from __future__ import annotations

from hashlib import sha256
from html import escape
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.texts import DEFAULT_LANGUAGE, LANGUAGE_LABELS, LANGUAGES, t
from app.config import Settings, get_settings
from app.data import repo
from app.engine import CheckInput, CheckResult, CheckStatus, InputType, Language, run_check
from app.engine.faces import FACES
from app.engine.format import format_status_message
from app.privacy.consent import is_consent_current
from app.web.abuse import pseudonymous_ip_key, read_limited_upload, require_turnstile_for_image
from app.web.content import available_languages, get_article, list_articles, sitemap_articles
from app.web.session import get_or_create_web_session, set_web_session_cookie

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).with_name("templates")))


def _static_version() -> str:
    """Fingerprint browser-cached assets so each deploy gets fresh URLs."""

    static_dir = Path(__file__).with_name("static")
    digest = sha256()
    for name in (
        "styles.css",
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
HREFLANGS = {"uz_latn": "uz-Latn", "uz_cyrl": "uz-Cyrl", "ru": "ru"}
DEV_WEB_SESSION_SECRET = "development-web-session-secret"
WEB_MAX_TEXT_CHARS = 6000
WEB_MAX_CAPTION_CHARS = 500
WEB_IP_FACE_PREFIX = "web_ip:"
WEB_BILLABLE_STATUSES = frozenset(
    {CheckStatus.ok, CheckStatus.no_signal, CheckStatus.safety_fallback}
)

WEB_COPY = {
    "uz_latn": {
        "html_lang": "uz-Latn",
        "nav_home": "Bosh sahifa",
        "nav_check": "Tekshirish",
        "nav_family": "Oila himoyasi",
        "nav_merchants": "Sotuvchi himoyasi",
        "nav_scams": "Firibgarlik turlari",
        "privacy_link": "Maxfiylik",
        "language_label": "Til",
        "product_label": "Bo'limlar",
        "workflow_label": "Qanday ishlaydi",
        "trust_label": "Ishonch",
        "skip_to_check": "Tekshiruvga o'tish",
        "landing_cta": "Xabarni tekshirish",
        "landing_preview_title": "Shubhani aniq tekshiruv rejasiga aylantiring.",
        "landing_steps_title": "Uch qadamda tekshiring",
        "landing_steps_lead": (
            "Xabarni kiriting, kerak bo'lsa skrinshot qo'shing va tekshiruv "
            "ro'yxatini oling."
        ),
        "title": "Avvalo",
        "scams_title": "Firibgarlik turlari",
        "scams_empty": "Hozircha maqolalar ko'rib chiqilmoqda.",
        "scams_fallback": "Bu maqola hozircha tanlangan tilda yo'q, mavjud tarjima ko'rsatildi.",
        "scams_cta": "Shubhali xabarni Avvalo orqali tekshiring",
        "scams_open": "O'qish",
        "privacy_title": "Maxfiylik",
        "consent_label": "Maxfiylik shartlarini o'qidim va roziman",
        "message_label": "Xabar matni",
        "caption_label": "Qo'shimcha izoh",
        "image_label": "Skrinshot yoki rasm",
        "submit": "Tekshirish",
        "checking": "Tekshirilmoqda...",
        "result_error_title": "Hozir tekshirib bo'lmadi",
        "result_empty": "Javob bo'sh keldi.",
        "meta_status": "Holat",
        "meta_latency": "Vaqt",
        "meta_cost": "Narx",
        "empty_error": "Tekshirish uchun xabar yozing yoki matni ko'rinadigan rasm yuklang.",
        "too_long_error": "Matn biroz uzun. Qisqartirib, qayta yuboring.",
        "consent_error": "Avval maxfiylik shartlariga rozilik bering.",
        "unknown_face_error": "Bunday tekshiruv turi topilmadi.",
        "faces": {
            "family": {
                "eyebrow": "Oilalar uchun",
                "name": "Oila himoyasi",
                "headline": "Javob berishdan yoki pul yuborishdan oldin Avvalo tekshirib ko'ring.",
                "subhead": (
                    "Xabar yoki skrinshotni yuboring. Avvalo xavf belgilarini, nimani "
                    "tekshirishni va qanday savol berishni aniq qilib beradi."
                ),
                "prompt": "Bank, qarindosh, yetkazib berish, ish, xarid yoki oldindan to'lov haqidagi xabarni shu yerga qo'ying.",
                "textarea_placeholder": "Masalan: SMS kodni ayting, aks holda karta bloklanadi...",
                "caption_placeholder": "Kerak bo'lsa: kim yubordi, nima so'rayapti?",
                "image_hint": "Rasmda matn aniq ko'rinsin. Rasm yuborilganda xavfsizlik tekshiruvi ishlaydi.",
                "trust": [
                    "Odamni emas, vaziyatni tekshiradi",
                    "Hukm emas, tekshiruv ro'yxati beradi",
                    "Yuborgan matningiz 1 soat ichida o'chiriladi",
                ],
            },
            "merchants": {
                "eyebrow": "Sotuvchilar uchun",
                "name": "Sotuvchi himoyasi",
                "headline": "Tovarni berishdan oldin to'lov va buyurtma xabarini tekshiring.",
                "subhead": (
                    "Avvalo chek, skrinshot, kuryer shoshiltirishi yoki qaytarim/refund so'rovini "
                    "bank ilovasida tekshiriladigan aniq qadamlarga ajratadi."
                ),
                "prompt": "Chek, buyurtma suhbati, kuryer yoki qaytarim haqidagi xabarni shu yerga qo'ying.",
                "textarea_placeholder": "Masalan: pul o'tdi, kuryer pastda kutyapti, tovarni bering...",
                "caption_placeholder": "Buyurtma summasi, to'lov vaqti yoki muhim detal",
                "image_hint": "Skrinshot to'lov dalili emas. Avvalo nimani bank ilovasida tekshirishni aytadi.",
                "trust": [
                    "Pul tushganini skrinshotga qarab tasdiqlamaydi",
                    "Bank ilovasida alohida tekshirishni eslatadi",
                    "Tovar ketishidan oldin xavf belgilarini ko'rsatadi",
                ],
            },
        },
    },
    "uz_cyrl": {
        "html_lang": "uz-Cyrl",
        "nav_home": "Бош саҳифа",
        "nav_check": "Текшириш",
        "nav_family": "Оила ҳимояси",
        "nav_merchants": "Сотувчи ҳимояси",
        "nav_scams": "Фирибгарлик турлари",
        "privacy_link": "Махфийлик",
        "language_label": "Тил",
        "product_label": "Бўлимлар",
        "workflow_label": "Қандай ишлайди",
        "trust_label": "Ишонч",
        "skip_to_check": "Текширувга ўтиш",
        "landing_cta": "Хабарни текшириш",
        "landing_preview_title": "Шубҳани аниқ текширув режасига айлантиринг.",
        "landing_steps_title": "Уч қадамда текширинг",
        "landing_steps_lead": (
            "Хабарни киритинг, керак бўлса скриншот қўшинг ва текширув "
            "рўйхатини олинг."
        ),
        "title": "Avvalo",
        "scams_title": "Фирибгарлик турлари",
        "scams_empty": "Ҳозирча мақолалар кўриб чиқилмоқда.",
        "scams_fallback": "Бу мақола ҳозирча танланган тилда йўқ, мавжуд таржима кўрсатилди.",
        "scams_cta": "Шубҳали хабарни Avvalo орқали текширинг",
        "scams_open": "Ўқиш",
        "privacy_title": "Махфийлик",
        "consent_label": "Махфийлик шартларини ўқидим ва розиман",
        "message_label": "Хабар матни",
        "caption_label": "Қўшимча изоҳ",
        "image_label": "Скриншот ёки расм",
        "submit": "Текшириш",
        "checking": "Текширилмоқда...",
        "result_error_title": "Ҳозир текшириб бўлмади",
        "result_empty": "Жавоб бўш келди.",
        "meta_status": "Ҳолат",
        "meta_latency": "Вақт",
        "meta_cost": "Нарх",
        "empty_error": "Текшириш учун хабар ёзинг ёки матни кўринадиган расм юкланг.",
        "too_long_error": "Матн бироз узун. Қисқартириб, қайта юборинг.",
        "consent_error": "Аввал махфийлик шартларига розилик беринг.",
        "unknown_face_error": "Бундай текширув тури топилмади.",
        "faces": {
            "family": {
                "eyebrow": "Оилалар учун",
                "name": "Оила ҳимояси",
                "headline": "Жавоб беришдан ёки пул юборишдан олдин Avvalo текшириб кўринг.",
                "subhead": (
                    "Хабар ёки скриншотни юборинг. Avvalo хавф белгиларини, нимани "
                    "текширишни ва қандай савол беришни аниқ қилиб беради."
                ),
                "prompt": "Банк, қариндош, етказиб бериш, иш, харид ёки олдиндан тўлов ҳақидаги хабарни шу ерга қўйинг.",
                "textarea_placeholder": "Масалан: SMS кодни айтинг, акс ҳолда карта блокланади...",
                "caption_placeholder": "Керак бўлса: ким юборди, нима сўраяпти?",
                "image_hint": "Расмда матн аниқ кўринсин. Расм юборилганда хавфсизлик текшируви ишлайди.",
                "trust": [
                    "Одамни эмас, вазиятни текширади",
                    "Ҳукм эмас, текширув рўйхати беради",
                    "Юборган матнингиз 1 соат ичида ўчирилади",
                ],
            },
            "merchants": {
                "eyebrow": "Сотувчилар учун",
                "name": "Сотувчи ҳимояси",
                "headline": "Товарни беришдан олдин тўлов ва буюртма хабарини текширинг.",
                "subhead": (
                    "Avvalo чек, скриншот, курьер шошилтириши ёки қайтарим/refund сўровини "
                    "банк иловасида текшириладиган аниқ қадамларга ажратади."
                ),
                "prompt": "Чек, буюртма суҳбати, курьер ёки қайтарим ҳақидаги хабарни шу ерга қўйинг.",
                "textarea_placeholder": "Масалан: пул ўтди, курьер пастда кутяпти, товарни беринг...",
                "caption_placeholder": "Буюртма суммаси, тўлов вақти ёки муҳим детал",
                "image_hint": "Скриншот тўлов далили эмас. Avvalo нимани банк иловасида текширишни айтади.",
                "trust": [
                    "Пул тушганини скриншотга қараб тасдиқламайди",
                    "Банк иловасида алоҳида текширишни эслатади",
                    "Товар кетишидан олдин хавф белгиларини кўрсатади",
                ],
            },
        },
    },
    "ru": {
        "html_lang": "ru",
        "nav_home": "Главная",
        "nav_check": "Проверить",
        "nav_family": "Защита семьи",
        "nav_merchants": "Защита продавца",
        "nav_scams": "Виды мошенничества",
        "privacy_link": "Конфиденциальность",
        "language_label": "Язык",
        "product_label": "Разделы",
        "workflow_label": "Как это работает",
        "trust_label": "Доверие",
        "skip_to_check": "Перейти к проверке",
        "landing_cta": "Проверить сообщение",
        "landing_preview_title": "Превратите сомнение в понятный план проверки.",
        "landing_steps_title": "Проверка в три шага",
        "landing_steps_lead": (
            "Вставьте сообщение, при необходимости добавьте скриншот и получите "
            "список проверок."
        ),
        "title": "Avvalo",
        "scams_title": "Виды мошенничества",
        "scams_empty": "Материалы пока на проверке.",
        "scams_fallback": "Этой статьи пока нет на выбранном языке, показан доступный перевод.",
        "scams_cta": "Проверить сомнительное сообщение в Avvalo",
        "scams_open": "Читать",
        "privacy_title": "Конфиденциальность",
        "consent_label": "Я прочитал условия конфиденциальности и согласен",
        "message_label": "Текст сообщения",
        "caption_label": "Короткий контекст",
        "image_label": "Скриншот или фото",
        "submit": "Проверить",
        "checking": "Проверяем...",
        "result_error_title": "Сейчас проверить не получилось",
        "result_empty": "Ответ пришёл пустым.",
        "meta_status": "Статус",
        "meta_latency": "Время",
        "meta_cost": "Стоимость",
        "empty_error": "Вставьте текст или загрузите читаемое изображение.",
        "too_long_error": "Текст получился слишком длинным. Сократите его и отправьте ещё раз.",
        "consent_error": "Сначала примите условия конфиденциальности.",
        "unknown_face_error": "Неизвестный тип проверки.",
        "faces": {
            "family": {
                "eyebrow": "Для семей",
                "name": "Защита семьи",
                "headline": "Перед ответом или оплатой проверьте сообщение в Avvalo.",
                "subhead": (
                    "Отправьте текст или скриншот. Avvalo покажет, где может быть риск, "
                    "что проверить и какой вопрос задать."
                ),
                "prompt": "Вставьте сообщение от банка, родственника, доставки, работодателя, продавца или покупателя.",
                "textarea_placeholder": "Например: скажите SMS-код, иначе карта будет заблокирована...",
                "caption_placeholder": "Если нужно: кто написал и чего просит?",
                "image_hint": "Текст на изображении должен быть читаемым. Для фото работает защитная проверка.",
                "trust": [
                    "Проверяем ситуацию, а не человека",
                    "Даём список проверок, а не ярлык",
                    "Ваш текст удаляется в течение 1 часа",
                ],
            },
            "merchants": {
                "eyebrow": "Для продавцов",
                "name": "Защита продавца",
                "headline": "Проверьте оплату и заказ до передачи товара.",
                "subhead": (
                    "Avvalo разбирает чек, переписку, давление курьером или запрос на возврат/refund "
                    "и превращает это в понятные проверки."
                ),
                "prompt": "Вставьте чек, переписку по заказу, запрос на доставку или возврат от покупателя.",
                "textarea_placeholder": "Например: деньги ушли, курьер уже ждёт, отдайте товар...",
                "caption_placeholder": "Сумма заказа, время оплаты или важная деталь",
                "image_hint": "Скриншот не доказывает оплату. Avvalo подскажет, что проверить в своём банке.",
                "trust": [
                    "Не подтверждает приход денег по скриншоту",
                    "Напоминает проверить свой банк отдельно",
                    "Показывает риски до передачи товара",
                ],
            },
        },
    },
}

FACE_PATHS = {
    "family": "/check",
    "merchants": "/merchants",
}


@router.get("/healthz")
async def healthz() -> dict[str, bool]:
    """Health check for local deploys and smoke tests."""

    return {"ok": True}


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, language: str = DEFAULT_LANGUAGE) -> HTMLResponse:
    """Render the public Avvalo landing page without a check form."""

    language = _normalize_language(language)
    copy = WEB_COPY[language]
    return templates.TemplateResponse(
        request,
        "landing.html",
        {
            "copy": copy,
            "face_copy": copy["faces"]["family"],
            "current_page": "home",
            "language_path": "/",
            "languages": LANGUAGES,
            "language_labels": LANGUAGE_LABELS,
            "language": language,
        },
    )


@router.get("/check", response_class=HTMLResponse)
async def family_check(request: Request, language: str = DEFAULT_LANGUAGE) -> HTMLResponse:
    """Render the consumer checker and its result surface."""

    return _face_page(request, face="family", language=language)


@router.get("/merchants", response_class=HTMLResponse)
async def merchants(request: Request, language: str = DEFAULT_LANGUAGE) -> HTMLResponse:
    """Render the Avvalo Merchants check page."""

    return _face_page(request, face="merchants", language=language)


@router.get("/scams", response_class=HTMLResponse)
async def scams_index(request: Request, language: str = DEFAULT_LANGUAGE) -> HTMLResponse:
    """Render the localized scam education index."""

    language = _normalize_language(language)
    copy = WEB_COPY[language]
    debug = _content_debug(request)
    response = templates.TemplateResponse(
        request,
        "scam_index.html",
        {
            "copy": copy,
            "language": language,
            "languages": LANGUAGES,
            "hreflangs": HREFLANGS,
            "language_labels": LANGUAGE_LABELS,
            "current_page": "scams",
            "language_path": "/scams",
            "articles": list_articles(language, include_drafts=debug),
        },
    )
    return _cache_content_response(response, debug=debug)


@router.get("/scams/{slug}", response_class=HTMLResponse)
async def scam_page(
    request: Request, slug: str, language: str = DEFAULT_LANGUAGE
) -> HTMLResponse:
    """Render one localized scam education page."""

    language = _normalize_language(language)
    debug = _content_debug(request)
    article = get_article(slug, language, include_drafts=debug)
    if article is None:
        raise HTTPException(status_code=404, detail="Scam page not found.")

    copy = WEB_COPY[language]
    response = templates.TemplateResponse(
        request,
        "scam_page.html",
        {
            "copy": copy,
            "language": language,
            "languages": LANGUAGES,
            "hreflangs": HREFLANGS,
            "language_labels": LANGUAGE_LABELS,
            "current_page": "scams",
            "language_path": f"/scams/{article.slug}",
            "article": article,
            "article_languages": available_languages(slug),
        },
    )
    return _cache_content_response(response, debug=debug)


@router.get("/sitemap.xml")
async def sitemap(request: Request) -> Response:
    """Return a sitemap of founder-reviewed published content."""

    base_url = str(request.base_url).rstrip("/")
    urls = [
        f"{base_url}/scams/{article.slug}?language={article.language}"
        for article in sitemap_articles()
    ]
    body = "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
            *[f"  <url><loc>{escape(url)}</loc></url>" for url in urls],
            "</urlset>",
            "",
        ]
    )
    return _cache_content_response(Response(content=body, media_type="application/xml"))


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
            "current_page": "check" if face == "family" else "merchant",
            "language_path": FACE_PATHS[face],
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
            "current_page": "privacy",
            "language_path": "/privacy",
            "privacy_text": t("privacy", language),
        },
    )


@router.post("/check", response_class=HTMLResponse)
async def check(
    request: Request,
    face: Annotated[str, Form()] = "family",
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
            raw_text=text if input_type is InputType.text else None,
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

        result = await run_check(
            check_input,
            session=session,
            settings=settings,
            rate_limit_override=settings.web_daily_limit,
        )
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


def _content_debug(request: Request) -> bool:
    return bool(getattr(request.app, "debug", False))


def _cache_content_response(response: HTMLResponse | Response, *, debug: bool = False) -> HTMLResponse | Response:
    response.headers["Cache-Control"] = (
        "no-store" if debug else "public, max-age=86400, stale-while-revalidate=604800"
    )
    return response
