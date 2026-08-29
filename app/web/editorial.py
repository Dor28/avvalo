"""Public editorial cases and the founder-only publishing interface."""

from __future__ import annotations

import asyncio
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.texts import DEFAULT_LANGUAGE, LANGUAGE_LABELS, LANGUAGES, normalize_language
from app.config import Settings
from app.content import (
    ARTICLE_MAX_CHARS,
    CATEGORIES,
    EDITORIAL_COVER_ALT_MAX_CHARS,
    EDITORIAL_COVER_UPLOAD_MAX_BYTES,
    SLUG_MAX_CHARS,
    SUMMARY_MAX_CHARS,
    TITLE_MAX_CHARS,
    EditorialPost,
    EditorialPostDraft,
    create_post,
    get_admin_cover,
    get_admin_post,
    get_published_cover,
    get_published_post,
    list_admin_posts,
    list_published_posts,
    prepare_editorial_cover,
    update_post,
)
from app.web.abuse import require_same_origin
from app.web.admin_auth import (
    access_key_matches,
    admin_no_store,
    admin_session_factory,
    admin_settings_or_404,
    clear_admin_cookie,
    is_admin_authenticated,
    require_admin,
    set_admin_cookie,
)
from app.web.editorial_copy import EDITORIAL_COPY
from app.web.knowledge_copy import KNOWLEDGE_COPY
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
        title_ru=title_ru,
        summary_ru=summary_ru,
        article_ru=article_ru,
    )


@router.get("/cases", response_class=HTMLResponse)
async def cases(request: Request, language: str = DEFAULT_LANGUAGE) -> HTMLResponse:
    """List published founder-authored educational cases."""

    language = normalize_language(language)
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
    return admin_no_store(response)


@router.get("/cases/{slug}", response_class=HTMLResponse)
async def case_detail(
    request: Request,
    slug: str,
    language: str = DEFAULT_LANGUAGE,
) -> HTMLResponse:
    """Render one published case; draft slugs remain indistinguishable from missing ones."""

    language = normalize_language(language)
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
    return admin_no_store(response)


@router.get("/cases/{slug}/cover", name="case_cover", include_in_schema=False)
async def case_cover(request: Request, slug: str) -> Response:
    """Serve a normalized cover only while its editorial post is published."""

    session_factory = _session_factory_or_none(request)
    if session_factory is None:
        raise HTTPException(status_code=404)
    async with session_factory() as session:
        cover = await get_published_cover(session, slug=slug)
    if cover is None:
        raise HTTPException(status_code=404)

    revision = int(cover.updated_ts.timestamp() * 1_000_000)
    etag = f'"{cover.post_id.hex}-{revision}"'
    headers = {
        "Cache-Control": "public, max-age=86400",
        "ETag": etag,
        "X-Content-Type-Options": "nosniff",
    }
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=cover.image_bytes, media_type=cover.media_type, headers=headers)


@router.get("/admin", include_in_schema=False)
async def admin_root(request: Request, language: str = DEFAULT_LANGUAGE) -> Response:
    """Send the founder to the editorial dashboard or its login screen."""

    settings = admin_settings_or_404(request)
    target = "/admin/posts" if is_admin_authenticated(request, settings) else "/admin/login"
    destination = f"{target}?language={normalize_language(language)}"
    return admin_no_store(RedirectResponse(destination, 303))


@router.get("/admin/login", response_class=HTMLResponse, include_in_schema=False)
async def admin_login(request: Request, language: str = DEFAULT_LANGUAGE) -> Response:
    """Render the founder-only access-key screen."""

    settings = admin_settings_or_404(request)
    language = normalize_language(language)
    if is_admin_authenticated(request, settings):
        return admin_no_store(RedirectResponse(f"/admin/posts?language={language}", 303))
    return _admin_login_response(request, language)


@router.post("/admin/login", response_class=HTMLResponse, include_in_schema=False)
async def admin_login_submit(
    request: Request,
    access_key: Annotated[str, Form()] = "",
    language: Annotated[str, Form()] = DEFAULT_LANGUAGE,
) -> Response:
    """Create a short-lived founder session after constant-time key validation."""

    require_same_origin(request)
    settings = admin_settings_or_404(request)
    language = normalize_language(language)
    if not access_key_matches(access_key, settings):
        return _admin_login_response(request, language, error=True, status_code=401)
    response = RedirectResponse(f"/admin/posts?language={language}", status_code=303)
    set_admin_cookie(response, settings, secure=_cookie_secure(request, settings))
    return admin_no_store(response)


@router.post("/admin/logout", include_in_schema=False)
async def admin_logout(
    request: Request,
    language: Annotated[str, Form()] = DEFAULT_LANGUAGE,
) -> Response:
    """Clear the dedicated founder session."""

    require_same_origin(request)
    admin_settings_or_404(request)
    response = RedirectResponse(
        f"/admin/login?language={normalize_language(language)}", status_code=303
    )
    clear_admin_cookie(response)
    return admin_no_store(response)


@router.get("/admin/posts", response_class=HTMLResponse, include_in_schema=False)
async def admin_posts(request: Request, language: str = DEFAULT_LANGUAGE) -> Response:
    """Render all drafts and published case posts."""

    settings = admin_settings_or_404(request)
    language = normalize_language(language)
    redirect = require_admin(request, settings, language)
    if redirect is not None:
        return redirect
    session_factory = admin_session_factory(request, detail="Editorial storage is not configured.")
    async with session_factory() as session:
        posts = await list_admin_posts(session)
    return admin_no_store(
        templates.TemplateResponse(
            request,
            "admin_posts.html",
            _admin_context(request, language, posts=posts),
        )
    )


@router.get("/admin/posts/new", response_class=HTMLResponse, include_in_schema=False)
async def admin_post_new(request: Request, language: str = DEFAULT_LANGUAGE) -> Response:
    """Render an empty trilingual post editor."""

    settings = admin_settings_or_404(request)
    language = normalize_language(language)
    redirect = require_admin(request, settings, language)
    if redirect is not None:
        return redirect
    return _admin_form_response(request, language, post=None)


@router.post("/admin/posts", response_class=HTMLResponse, include_in_schema=False)
async def admin_post_create(
    request: Request,
    draft: Annotated[EditorialPostDraft, Depends(_editorial_draft_from_form)],
    cover_image: Annotated[UploadFile | None, File()] = None,
    cover_alt_uz_latn: Annotated[str, Form()] = "",
    cover_alt_ru: Annotated[str, Form()] = "",
    remove_cover: Annotated[bool, Form()] = False,
    language: Annotated[str, Form()] = DEFAULT_LANGUAGE,
) -> Response:
    """Validate and create one founder-authored post."""

    require_same_origin(request)
    settings = admin_settings_or_404(request)
    language = normalize_language(language)
    redirect = require_admin(request, settings, language)
    if redirect is not None:
        return redirect
    return await _save_admin_post(
        request,
        language=language,
        draft=draft,
        post_id=None,
        cover_image=cover_image,
        cover_alt_uz_latn=cover_alt_uz_latn,
        cover_alt_ru=cover_alt_ru,
        remove_cover=remove_cover,
    )


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

    settings = admin_settings_or_404(request)
    language = normalize_language(language)
    redirect = require_admin(request, settings, language)
    if redirect is not None:
        return redirect
    session_factory = admin_session_factory(request, detail="Editorial storage is not configured.")
    async with session_factory() as session:
        post = await get_admin_post(session, post_id)
    if post is None:
        raise HTTPException(status_code=404)
    return _admin_form_response(request, language, post=post)


@router.get(
    "/admin/posts/{post_id}/cover",
    include_in_schema=False,
)
async def admin_post_cover(request: Request, post_id: uuid.UUID) -> Response:
    """Preview a cover inside the authenticated editor, including for drafts."""

    settings = admin_settings_or_404(request)
    if not is_admin_authenticated(request, settings):
        raise HTTPException(status_code=404)
    session_factory = admin_session_factory(request, detail="Editorial storage is not configured.")
    async with session_factory() as session:
        cover = await get_admin_cover(session, post_id)
    if cover is None:
        raise HTTPException(status_code=404)
    return admin_no_store(
        Response(
            content=cover.image_bytes,
            media_type=cover.media_type,
            headers={"X-Content-Type-Options": "nosniff"},
        )
    )


@router.post(
    "/admin/posts/{post_id}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def admin_post_update(
    request: Request,
    post_id: uuid.UUID,
    draft: Annotated[EditorialPostDraft, Depends(_editorial_draft_from_form)],
    cover_image: Annotated[UploadFile | None, File()] = None,
    cover_alt_uz_latn: Annotated[str, Form()] = "",
    cover_alt_ru: Annotated[str, Form()] = "",
    remove_cover: Annotated[bool, Form()] = False,
    language: Annotated[str, Form()] = DEFAULT_LANGUAGE,
) -> Response:
    """Validate and update an existing founder-authored post."""

    require_same_origin(request)
    settings = admin_settings_or_404(request)
    language = normalize_language(language)
    redirect = require_admin(request, settings, language)
    if redirect is not None:
        return redirect
    return await _save_admin_post(
        request,
        language=language,
        draft=draft,
        post_id=post_id,
        cover_image=cover_image,
        cover_alt_uz_latn=cover_alt_uz_latn,
        cover_alt_ru=cover_alt_ru,
        remove_cover=remove_cover,
    )


async def _save_admin_post(
    request: Request,
    *,
    language: str,
    draft: EditorialPostDraft,
    post_id: uuid.UUID | None,
    cover_image: UploadFile | None,
    cover_alt_uz_latn: str,
    cover_alt_ru: str,
    remove_cover: bool,
) -> Response:
    session_factory = admin_session_factory(request, detail="Editorial storage is not configured.")
    error_key: str | None = None
    post: EditorialPost | EditorialPostDraft | None = draft
    try:
        async with session_factory() as session:
            if post_id is None:
                current_has_cover = False
            else:
                existing = await get_admin_post(session, post_id)
                if existing is None:
                    raise HTTPException(status_code=404)
                post = existing
                current_has_cover = existing.cover_media_type is not None

            uploaded_bytes = await _read_cover_upload(cover_image)
            cover = await asyncio.to_thread(
                prepare_editorial_cover,
                image_bytes=uploaded_bytes,
                alt_uz_latn=cover_alt_uz_latn,
                alt_ru=cover_alt_ru,
                remove=remove_cover,
                current_has_cover=current_has_cover,
            )
            if post_id is None:
                await create_post(session, draft, cover)
            else:
                await update_post(session, existing, draft, cover)
            await session.commit()
    except IntegrityError:
        error_key = "duplicate_slug"
    except ValueError as exc:
        error_key = _editorial_error_key(exc)
    if error_key is not None:
        return _admin_form_response(
            request,
            language,
            post=post,
            error=EDITORIAL_COPY[language][error_key],
            cover_alts={"uz_latn": cover_alt_uz_latn, "ru": cover_alt_ru},
            status_code=409 if error_key == "duplicate_slug" else 400,
        )
    return admin_no_store(RedirectResponse(f"/admin/posts?language={language}", status_code=303))


def _admin_login_response(
    request: Request,
    language: str,
    *,
    error: bool = False,
    status_code: int = 200,
) -> HTMLResponse:
    return admin_no_store(
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
    cover_alts: dict[str, str] | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    cover_alt_values = cover_alts or {
        language_code: getattr(post, f"cover_alt_{language_code}", "") or ""
        for language_code in LANGUAGES
    }
    return admin_no_store(
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
                max_cover_alt=EDITORIAL_COVER_ALT_MAX_CHARS,
                cover_alt_values=cover_alt_values,
            ),
            status_code=status_code,
        )
    )


async def _read_cover_upload(upload: UploadFile | None) -> bytes | None:
    if upload is None or not upload.filename:
        return None
    content = await upload.read(EDITORIAL_COVER_UPLOAD_MAX_BYTES + 1)
    if len(content) > EDITORIAL_COVER_UPLOAD_MAX_BYTES:
        raise ValueError("cover_too_large")
    return content


def _editorial_error_key(exc: ValueError) -> str:
    code = exc.args[0] if exc.args and isinstance(exc.args[0], str) else ""
    return {
        "invalid_cover": "cover_invalid",
        "cover_too_large": "cover_too_large",
        "cover_alt_required": "cover_alt_required",
        "cover_alt_too_long": "cover_alt_too_long",
        "cover_alt_without_image": "cover_alt_without_image",
    }.get(code, "form_error")


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
        "cards_nav_label": KNOWLEDGE_COPY[language]["title"],
        **extra,
    }


def _session_factory_or_none(request: Request) -> async_sessionmaker[AsyncSession] | None:
    return getattr(request.app.state, "session_factory", None)


def _cookie_secure(request: Request, settings: Settings) -> bool:
    if settings.web_cookie_secure:
        return True
    forwarded = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip()
    return request.url.scheme.casefold() == "https" or forwarded.casefold() == "https"
