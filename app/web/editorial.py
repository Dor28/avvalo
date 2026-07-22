"""Public editorial cases and the founder-only publishing interface."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.texts import DEFAULT_LANGUAGE, LANGUAGE_LABELS, LANGUAGES
from app.config import Settings
from app.content import (
    ARTICLE_MAX_CHARS,
    CATEGORIES,
    SLUG_MAX_CHARS,
    SUMMARY_MAX_CHARS,
    TITLE_MAX_CHARS,
    EditorialPost,
    EditorialPostDraft,
    create_post,
    get_admin_post,
    get_published_post,
    list_admin_posts,
    list_published_posts,
    update_post,
)
from app.web.abuse import require_same_origin
from app.web.admin_auth import (
    access_key_matches,
    clear_admin_cookie,
    is_admin_authenticated,
    set_admin_cookie,
)
from app.web.editorial_copy import EDITORIAL_COPY
from app.web.routes import WEB_COPY, templates
from app.web.rules_copy import RULES_COPY

router = APIRouter()


def _editorial_draft_from_form(
    slug: Annotated[str, Form()] = "",
    category: Annotated[str, Form()] = "",
    state: Annotated[str, Form()] = "",
    title_uz_latn: Annotated[str, Form()] = "",
    summary_uz_latn: Annotated[str, Form()] = "",
    article_uz_latn: Annotated[str, Form()] = "",
    title_uz_cyrl: Annotated[str, Form()] = "",
    summary_uz_cyrl: Annotated[str, Form()] = "",
    article_uz_cyrl: Annotated[str, Form()] = "",
    title_ru: Annotated[str, Form()] = "",
    summary_ru: Annotated[str, Form()] = "",
    article_ru: Annotated[str, Form()] = "",
) -> EditorialPostDraft:
    """Build the typed editorial boundary from flat browser form fields."""

    return EditorialPostDraft(
        slug=slug,
        category=category,
        state=state,
        title_uz_latn=title_uz_latn,
        summary_uz_latn=summary_uz_latn,
        article_uz_latn=article_uz_latn,
        title_uz_cyrl=title_uz_cyrl,
        summary_uz_cyrl=summary_uz_cyrl,
        article_uz_cyrl=article_uz_cyrl,
        title_ru=title_ru,
        summary_ru=summary_ru,
        article_ru=article_ru,
    )


@router.get("/cases", response_class=HTMLResponse)
async def cases(request: Request, language: str = DEFAULT_LANGUAGE) -> HTMLResponse:
    """List published founder-authored educational cases."""

    language = _normalize_language(language)
    posts = []
    session_factory = _session_factory_or_none(request)
    if session_factory is not None:
        async with session_factory() as session:
            posts = await list_published_posts(session, language=language)
    response = templates.TemplateResponse(
        request,
        "cases.html",
        _public_context(request, language, language_path="/cases", posts=posts),
    )
    return _no_store(response)


@router.get("/cases/{slug}", response_class=HTMLResponse)
async def case_detail(
    request: Request,
    slug: str,
    language: str = DEFAULT_LANGUAGE,
) -> HTMLResponse:
    """Render one published case; draft slugs remain indistinguishable from missing ones."""

    language = _normalize_language(language)
    session_factory = _session_factory_or_none(request)
    if session_factory is None:
        raise HTTPException(status_code=404)
    async with session_factory() as session:
        post = await get_published_post(session, slug=slug, language=language)
    if post is None:
        raise HTTPException(status_code=404)
    response = templates.TemplateResponse(
        request,
        "case_detail.html",
        _public_context(
            request,
            language,
            language_path=f"/cases/{post.slug}",
            post=post,
        ),
    )
    return _no_store(response)


@router.get("/admin", include_in_schema=False)
async def admin_root(request: Request, language: str = DEFAULT_LANGUAGE) -> Response:
    """Send the founder to the editorial dashboard or its login screen."""

    settings = _admin_settings(request)
    target = "/admin/posts" if is_admin_authenticated(request, settings) else "/admin/login"
    return _no_store(RedirectResponse(f"{target}?language={_normalize_language(language)}", 303))


@router.get("/admin/login", response_class=HTMLResponse, include_in_schema=False)
async def admin_login(request: Request, language: str = DEFAULT_LANGUAGE) -> Response:
    """Render the founder-only access-key screen."""

    settings = _admin_settings(request)
    language = _normalize_language(language)
    if is_admin_authenticated(request, settings):
        return _no_store(RedirectResponse(f"/admin/posts?language={language}", 303))
    return _admin_login_response(request, language)


@router.post("/admin/login", response_class=HTMLResponse, include_in_schema=False)
async def admin_login_submit(
    request: Request,
    access_key: Annotated[str, Form()] = "",
    language: Annotated[str, Form()] = DEFAULT_LANGUAGE,
) -> Response:
    """Create a short-lived founder session after constant-time key validation."""

    require_same_origin(request)
    settings = _admin_settings(request)
    language = _normalize_language(language)
    if not access_key_matches(access_key, settings):
        return _admin_login_response(request, language, error=True, status_code=401)
    response = RedirectResponse(f"/admin/posts?language={language}", status_code=303)
    set_admin_cookie(response, settings, secure=_cookie_secure(request, settings))
    return _no_store(response)


@router.post("/admin/logout", include_in_schema=False)
async def admin_logout(
    request: Request,
    language: Annotated[str, Form()] = DEFAULT_LANGUAGE,
) -> Response:
    """Clear the dedicated founder session."""

    require_same_origin(request)
    _admin_settings(request)
    response = RedirectResponse(
        f"/admin/login?language={_normalize_language(language)}", status_code=303
    )
    clear_admin_cookie(response)
    return _no_store(response)


@router.get("/admin/posts", response_class=HTMLResponse, include_in_schema=False)
async def admin_posts(request: Request, language: str = DEFAULT_LANGUAGE) -> Response:
    """Render all drafts and published case posts."""

    settings = _admin_settings(request)
    language = _normalize_language(language)
    redirect = _require_admin(request, settings, language)
    if redirect is not None:
        return redirect
    session_factory = _session_factory_or_error(request)
    async with session_factory() as session:
        posts = await list_admin_posts(session)
    return _no_store(
        templates.TemplateResponse(
            request,
            "admin_posts.html",
            _admin_context(request, language, posts=posts),
        )
    )


@router.get("/admin/posts/new", response_class=HTMLResponse, include_in_schema=False)
async def admin_post_new(request: Request, language: str = DEFAULT_LANGUAGE) -> Response:
    """Render an empty trilingual post editor."""

    settings = _admin_settings(request)
    language = _normalize_language(language)
    redirect = _require_admin(request, settings, language)
    if redirect is not None:
        return redirect
    return _admin_form_response(request, language, post=None)


@router.post("/admin/posts", response_class=HTMLResponse, include_in_schema=False)
async def admin_post_create(
    request: Request,
    draft: Annotated[EditorialPostDraft, Depends(_editorial_draft_from_form)],
    language: Annotated[str, Form()] = DEFAULT_LANGUAGE,
) -> Response:
    """Validate and create one founder-authored post."""

    require_same_origin(request)
    settings = _admin_settings(request)
    language = _normalize_language(language)
    redirect = _require_admin(request, settings, language)
    if redirect is not None:
        return redirect
    return await _save_admin_post(request, language=language, draft=draft, post_id=None)


@router.get(
    "/admin/posts/{post_id}/edit",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def admin_post_edit(
    request: Request,
    post_id: uuid.UUID,
    language: str = DEFAULT_LANGUAGE,
) -> Response:
    """Render an existing post in the trilingual editor."""

    settings = _admin_settings(request)
    language = _normalize_language(language)
    redirect = _require_admin(request, settings, language)
    if redirect is not None:
        return redirect
    session_factory = _session_factory_or_error(request)
    async with session_factory() as session:
        post = await get_admin_post(session, post_id)
    if post is None:
        raise HTTPException(status_code=404)
    return _admin_form_response(request, language, post=post)


@router.post(
    "/admin/posts/{post_id}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def admin_post_update(
    request: Request,
    post_id: uuid.UUID,
    draft: Annotated[EditorialPostDraft, Depends(_editorial_draft_from_form)],
    language: Annotated[str, Form()] = DEFAULT_LANGUAGE,
) -> Response:
    """Validate and update an existing founder-authored post."""

    require_same_origin(request)
    settings = _admin_settings(request)
    language = _normalize_language(language)
    redirect = _require_admin(request, settings, language)
    if redirect is not None:
        return redirect
    return await _save_admin_post(request, language=language, draft=draft, post_id=post_id)


async def _save_admin_post(
    request: Request,
    *,
    language: str,
    draft: EditorialPostDraft,
    post_id: uuid.UUID | None,
) -> Response:
    session_factory = _session_factory_or_error(request)
    error_key: str | None = None
    post: EditorialPost | EditorialPostDraft | None = draft
    try:
        async with session_factory() as session:
            if post_id is None:
                await create_post(session, draft)
            else:
                existing = await get_admin_post(session, post_id)
                if existing is None:
                    raise HTTPException(status_code=404)
                post = existing
                await update_post(session, existing, draft)
            await session.commit()
    except IntegrityError:
        error_key = "duplicate_slug"
    except ValueError:
        error_key = "form_error"
    if error_key is not None:
        return _admin_form_response(
            request,
            language,
            post=post,
            error=EDITORIAL_COPY[language][error_key],
            status_code=409 if error_key == "duplicate_slug" else 400,
        )
    return _no_store(RedirectResponse(f"/admin/posts?language={language}", status_code=303))


def _admin_login_response(
    request: Request,
    language: str,
    *,
    error: bool = False,
    status_code: int = 200,
) -> HTMLResponse:
    return _no_store(
        templates.TemplateResponse(
            request,
            "admin_login.html",
            _admin_context(request, language, login_error=error),
            status_code=status_code,
        )
    )


def _admin_form_response(
    request: Request,
    language: str,
    *,
    post: EditorialPost | EditorialPostDraft | None,
    error: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    return _no_store(
        templates.TemplateResponse(
            request,
            "admin_post_form.html",
            _admin_context(
                request,
                language,
                post=post,
                error=error,
                max_slug=SLUG_MAX_CHARS,
                max_title=TITLE_MAX_CHARS,
                max_summary=SUMMARY_MAX_CHARS,
                max_article=ARTICLE_MAX_CHARS,
            ),
            status_code=status_code,
        )
    )


def _public_context(request: Request, language: str, *, language_path: str, **extra) -> dict:
    return {
        "request": request,
        "copy": WEB_COPY[language],
        "editorial": EDITORIAL_COPY[language],
        "language": language,
        "languages": LANGUAGES,
        "language_labels": LANGUAGE_LABELS,
        "language_path": language_path,
        **extra,
    }


def _admin_context(request: Request, language: str, **extra) -> dict:
    return {
        "request": request,
        "copy": WEB_COPY[language],
        "editorial": EDITORIAL_COPY[language],
        "language": language,
        "languages": LANGUAGES,
        "language_labels": LANGUAGE_LABELS,
        "categories": CATEGORIES,
        "rules_nav_label": RULES_COPY[language]["title"],
        **extra,
    }


def _admin_settings(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    if settings is None or settings.admin_access_key is None:
        raise HTTPException(status_code=404)
    if not settings.admin_access_key.get_secret_value():
        raise HTTPException(status_code=404)
    return settings


def _require_admin(
    request: Request,
    settings: Settings,
    language: str,
) -> RedirectResponse | None:
    if is_admin_authenticated(request, settings):
        return None
    return _no_store(RedirectResponse(f"/admin/login?language={language}", status_code=303))


def _session_factory_or_none(request: Request) -> async_sessionmaker[AsyncSession] | None:
    return getattr(request.app.state, "session_factory", None)


def _session_factory_or_error(request: Request) -> async_sessionmaker[AsyncSession]:
    session_factory = _session_factory_or_none(request)
    if session_factory is None:
        raise HTTPException(status_code=503, detail="Editorial storage is not configured.")
    return session_factory


def _normalize_language(language: str) -> str:
    return language if language in LANGUAGES else DEFAULT_LANGUAGE


def _cookie_secure(request: Request, settings: Settings) -> bool:
    if settings.web_cookie_secure:
        return True
    forwarded = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip()
    return request.url.scheme.casefold() == "https" or forwarded.casefold() == "https"


def _no_store(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response
