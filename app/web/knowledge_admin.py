"""Operator-only editor for the knowledge cards layered onto the shipped base.

A card can be well formed, save cleanly, and still never be retrieved, because
selection runs on ``trigger_rule_ids``, ``trigger_signal_kinds``, and
``retrieval_aliases`` rather than on the card body. The dry-run exists to make
that visible, and it drives the real ``retrieve_knowledge`` so it cannot drift
from production.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.texts import DEFAULT_LANGUAGE, LANGUAGE_LABELS, LANGUAGES
from app.config import Settings
from app.engine.knowledge.loader import FileKnowledgeStore, load_yaml_knowledge_base
from app.knowledge_store import (
    CardPreview,
    KnowledgeCardDraft,
    KnowledgeCardOverride,
    create_card,
    delete_card,
    get_card,
    list_cards,
    preview_card,
    refresh_knowledge_base,
    update_card,
)
from app.knowledge_store.repo import LANGUAGES as ALIAS_LANGUAGES
from app.knowledge_store.repo import STATUSES
from app.web.abuse import require_same_origin
from app.web.admin_auth import is_admin_authenticated
from app.web.editorial_copy import EDITORIAL_COPY
from app.web.knowledge_copy import KNOWLEDGE_COPY, SCRIPT_LABELS
from app.web.routes import WEB_COPY, templates
from app.web.rules_copy import RULES_COPY

router = APIRouter()


def _draft_from_form(
    card_id: Annotated[str, Form()] = "",
    card_version: Annotated[str, Form()] = "",
    status: Annotated[str, Form()] = "approved",
    reviewer: Annotated[str, Form()] = "",
    mechanism: Annotated[str, Form()] = "",
    trigger_rule_ids: Annotated[str, Form()] = "",
    trigger_signal_kinds: Annotated[str, Form()] = "",
    red_flags: Annotated[str, Form()] = "",
    verify_steps: Annotated[str, Form()] = "",
    questions: Annotated[str, Form()] = "",
    reviewed_case_ids: Annotated[str, Form()] = "",
    aliases_uz_latn: Annotated[str, Form()] = "",
    aliases_uz_cyrl: Annotated[str, Form()] = "",
    aliases_ru: Annotated[str, Form()] = "",
) -> KnowledgeCardDraft:
    """Build the typed boundary from flat browser form fields."""

    return KnowledgeCardDraft(
        card_id=card_id,
        card_version=card_version,
        status=status,
        reviewer=reviewer,
        mechanism=mechanism,
        trigger_rule_ids=_split(trigger_rule_ids),
        trigger_signal_kinds=_split(trigger_signal_kinds),
        red_flags=_split(red_flags),
        verify_steps=_split(verify_steps),
        questions=_split(questions),
        reviewed_case_ids=_split(reviewed_case_ids),
        retrieval_aliases={
            "uz_latn": _split(aliases_uz_latn),
            "uz_cyrl": _split(aliases_uz_cyrl),
            "ru": _split(aliases_ru),
        },
    )


def _split(raw: str) -> list[str]:
    """One entry per line; blank lines are ignored rather than rejected."""

    return [line.strip() for line in raw.splitlines() if line.strip()]


@router.get("/admin/cards", response_class=HTMLResponse, include_in_schema=False)
async def admin_cards(request: Request, language: str = DEFAULT_LANGUAGE) -> Response:
    """List every card override alongside the baseline size."""

    settings = _admin_settings(request)
    language = _normalize_language(language)
    redirect = _require_admin(request, settings, language)
    if redirect is not None:
        return redirect

    session_factory = _session_factory_or_error(request)
    async with session_factory() as session:
        overrides = await list_cards(session)
    return _no_store(
        templates.TemplateResponse(
            request,
            "admin_cards.html",
            _context(
                request,
                language,
                overrides=overrides,
                baseline_count=len(load_yaml_knowledge_base().cards),
                active_count=len(FileKnowledgeStore().load().cards),
            ),
        )
    )


@router.get("/admin/cards/new", response_class=HTMLResponse, include_in_schema=False)
async def admin_card_new(request: Request, language: str = DEFAULT_LANGUAGE) -> Response:
    """Render an empty card editor."""

    settings = _admin_settings(request)
    language = _normalize_language(language)
    redirect = _require_admin(request, settings, language)
    if redirect is not None:
        return redirect
    return _form_response(request, language, override=None)


@router.get(
    "/admin/cards/{override_id}/edit",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def admin_card_edit(
    request: Request,
    override_id: uuid.UUID,
    language: str = DEFAULT_LANGUAGE,
) -> Response:
    """Render an existing card override in the editor."""

    settings = _admin_settings(request)
    language = _normalize_language(language)
    redirect = _require_admin(request, settings, language)
    if redirect is not None:
        return redirect
    session_factory = _session_factory_or_error(request)
    async with session_factory() as session:
        override = await get_card(session, override_id)
    if override is None:
        raise HTTPException(status_code=404)
    return _form_response(request, language, override=override)


@router.post("/admin/cards/preview", response_class=HTMLResponse, include_in_schema=False)
async def admin_card_preview(
    request: Request,
    draft: Annotated[KnowledgeCardDraft, Depends(_draft_from_form)],
    sample: Annotated[str, Form()] = "",
    override_id: Annotated[str, Form()] = "",
    language: Annotated[str, Form()] = DEFAULT_LANGUAGE,
) -> Response:
    """Dry-run retrieval for the edited card without saving anything."""

    require_same_origin(request)
    settings = _admin_settings(request)
    language = _normalize_language(language)
    redirect = _require_admin(request, settings, language)
    if redirect is not None:
        return redirect

    preview: CardPreview | None = None
    error: str | None = None
    try:
        preview = await preview_card(draft, sample, FileKnowledgeStore().load())
    except ValueError as exc:
        error = _error_text(language, str(exc))

    return _form_response(
        request,
        language,
        override=draft,
        override_id=override_id or None,
        error=error,
        sample=sample,
        # Distinguish "ran and selected nothing" from "never ran".
        preview=preview if error is None and sample.strip() else None,
    )


@router.post("/admin/cards", response_class=HTMLResponse, include_in_schema=False)
async def admin_card_save(
    request: Request,
    draft: Annotated[KnowledgeCardDraft, Depends(_draft_from_form)],
    override_id: Annotated[str, Form()] = "",
    sample: Annotated[str, Form()] = "",
    language: Annotated[str, Form()] = DEFAULT_LANGUAGE,
) -> Response:
    """Create or update one card override, then republish the merged base."""

    require_same_origin(request)
    settings = _admin_settings(request)
    language = _normalize_language(language)
    redirect = _require_admin(request, settings, language)
    if redirect is not None:
        return redirect

    session_factory = _session_factory_or_error(request)
    error: str | None = None
    try:
        async with session_factory() as session:
            if override_id:
                existing = await get_card(session, uuid.UUID(override_id))
                if existing is None:
                    raise HTTPException(status_code=404)
                await update_card(session, existing, draft)
            else:
                await create_card(session, draft)
            await session.commit()
            # Republish immediately: waiting out the refresh interval would
            # leave the operator unable to tell whether the edit took effect.
            await refresh_knowledge_base(session)
    except IntegrityError:
        error = _error_text(language, "duplicate_card")
    except ValueError as exc:
        error = _error_text(language, str(exc))

    if error is not None:
        return _form_response(
            request,
            language,
            override=draft,
            override_id=override_id or None,
            error=error,
            sample=sample,
            status_code=400,
        )
    return _no_store(RedirectResponse(f"/admin/cards?language={language}", status_code=303))


@router.post("/admin/cards/{override_id}/delete", include_in_schema=False)
async def admin_card_delete(
    request: Request,
    override_id: uuid.UUID,
    language: Annotated[str, Form()] = DEFAULT_LANGUAGE,
) -> Response:
    """Delete a card override so the shipped baseline card applies again."""

    require_same_origin(request)
    settings = _admin_settings(request)
    language = _normalize_language(language)
    redirect = _require_admin(request, settings, language)
    if redirect is not None:
        return redirect

    session_factory = _session_factory_or_error(request)
    async with session_factory() as session:
        override = await get_card(session, override_id)
        if override is None:
            raise HTTPException(status_code=404)
        await delete_card(session, override)
        await session.commit()
        await refresh_knowledge_base(session)
    return _no_store(RedirectResponse(f"/admin/cards?language={language}", status_code=303))


def _form_response(
    request: Request,
    language: str,
    *,
    override: KnowledgeCardOverride | KnowledgeCardDraft | None,
    override_id: str | None = None,
    error: str | None = None,
    sample: str = "",
    preview: CardPreview | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    resolved_id = override_id or (
        str(override.id) if isinstance(override, KnowledgeCardOverride) else None
    )
    return _no_store(
        templates.TemplateResponse(
            request,
            "admin_card_form.html",
            _context(
                request,
                language,
                override=override,
                override_id=resolved_id,
                fields=_fields_for_form(override),
                aliases=_aliases_for_form(override),
                alias_languages=ALIAS_LANGUAGES,
                statuses=STATUSES,
                error=error,
                sample=sample,
                preview=preview,
            ),
            status_code=status_code,
        )
    )


_LIST_FIELDS = (
    "trigger_rule_ids",
    "trigger_signal_kinds",
    "red_flags",
    "verify_steps",
    "questions",
    "reviewed_case_ids",
)


def _fields_for_form(
    override: KnowledgeCardOverride | KnowledgeCardDraft | None,
) -> dict[str, str]:
    """Render stored list fields back into one-per-line textarea values."""

    return {
        field: "\n".join(getattr(override, field, None) or []) if override else ""
        for field in _LIST_FIELDS
    }


def _aliases_for_form(
    override: KnowledgeCardOverride | KnowledgeCardDraft | None,
) -> dict[str, str]:
    stored = getattr(override, "retrieval_aliases", None) or {}
    return {
        language: "\n".join(stored.get(language, []) or []) for language in ALIAS_LANGUAGES
    }


def _error_text(language: str, key: str) -> str:
    errors = KNOWLEDGE_COPY[language]["errors"]
    return errors.get(key, errors["invalid_aliases"])


def _context(request: Request, language: str, **extra) -> dict:
    return {
        "request": request,
        "copy": WEB_COPY[language],
        "editorial": EDITORIAL_COPY[language],
        "knowledge": KNOWLEDGE_COPY[language],
        "language": language,
        "languages": LANGUAGES,
        "language_labels": LANGUAGE_LABELS,
        "script_labels": SCRIPT_LABELS,
        "rules_nav_label": RULES_COPY[language]["title"],
        "cards_nav_label": KNOWLEDGE_COPY[language]["title"],
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
    request: Request, settings: Settings, language: str
) -> RedirectResponse | None:
    if is_admin_authenticated(request, settings):
        return None
    return _no_store(RedirectResponse(f"/admin/login?language={language}", status_code=303))


def _session_factory_or_error(request: Request) -> async_sessionmaker[AsyncSession]:
    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory is None:
        raise HTTPException(status_code=503, detail="Knowledge storage is not configured.")
    return session_factory


def _normalize_language(language: str) -> str:
    return language if language in LANGUAGES else DEFAULT_LANGUAGE


def _no_store(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response
