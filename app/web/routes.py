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


@router.get("/healthz")
async def healthz() -> dict[str, bool]:
    """Health check for local deploys and smoke tests."""

    return {"ok": True}


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Render the anonymous check form."""

    settings = _settings_or_none(request)
    web_session = get_or_create_web_session(request, secret=_web_secret(settings))
    response = templates.TemplateResponse(
        request,
        "index.html",
        {
            "languages": LANGUAGES,
            "language_labels": LANGUAGE_LABELS,
            "default_language": DEFAULT_LANGUAGE,
            "faces": FACES,
            "privacy_text": t("privacy_notice", DEFAULT_LANGUAGE),
            "turnstile_site_key": (
                settings.turnstile_site_key.get_secret_value()
                if settings and settings.turnstile_site_key
                else None
            ),
        },
    )
    set_web_session_cookie(response, web_session)
    return response


@router.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request, language: str = DEFAULT_LANGUAGE) -> HTMLResponse:
    """Render the localized privacy notice."""

    if language not in LANGUAGES:
        language = DEFAULT_LANGUAGE
    return templates.TemplateResponse(
        request,
        "privacy.html",
        {
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
    if face not in FACES:
        raise HTTPException(status_code=400, detail="Unknown face.")
    if language not in LANGUAGES:
        language = DEFAULT_LANGUAGE

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
            error="Please paste text or upload a readable image.",
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
                error="Please accept the privacy notice first.",
                web_session=web_session,
            )
        result = await run_check(
            check_input,
            settings=settings,
            rate_limit_override=settings.web_daily_limit,
        )
        return _partial(request, result=result, web_session=web_session)

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
                error="Please accept the privacy notice first.",
                web_session=web_session,
            )

        result = await run_check(
            check_input,
            session=session,
            settings=settings,
            rate_limit_override=settings.web_daily_limit,
        )
        await session.commit()

    return _partial(request, result=result, web_session=web_session)


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
    status_code: int = 200,
    web_session=None,
) -> HTMLResponse:
    response = templates.TemplateResponse(
        request,
        "_result.html",
        {"result": result, "error": error},
        status_code=status_code,
    )
    if web_session is not None:
        set_web_session_cookie(response, web_session)
    return response


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
