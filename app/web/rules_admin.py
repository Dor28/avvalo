"""Operator-only editor for the rule overrides layered onto the shipped pack.

Editing detection patterns through a form is safety-critical: a bad pattern
degrades detection silently for every user, and this box deploys from ``main``.
Every route therefore forces a dry-run affordance and republishes the merged
pack immediately on save, so an operator sees the real effect rather than
waiting out the refresh interval.
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
from app.engine.rules.loader import load_rule_pack, load_yaml_rule_pack
from app.rules_store import (
    RuleOverride,
    RuleOverrideDraft,
    create_override,
    delete_override,
    get_override,
    list_overrides,
    preview_rule,
    refresh_rule_pack,
    update_override,
)
from app.rules_store.repo import LANGUAGES as PATTERN_LANGUAGES
from app.web.abuse import require_same_origin
from app.web.admin_auth import is_admin_authenticated
from app.web.editorial_copy import EDITORIAL_COPY
from app.web.routes import WEB_COPY, templates
from app.web.rules_copy import RULES_COPY

router = APIRouter()

FACE = "family"


def _draft_from_form(
    rule_id: Annotated[str, Form()] = "",
    family: Annotated[str, Form()] = "",
    description: Annotated[str, Form()] = "",
    message_key: Annotated[str, Form()] = "",
    severity: Annotated[int, Form()] = 2,
    emits_signal: Annotated[str, Form()] = "",
    disabled: Annotated[bool, Form()] = False,
    patterns_uz_latn: Annotated[str, Form()] = "",
    patterns_uz_cyrl: Annotated[str, Form()] = "",
    patterns_ru: Annotated[str, Form()] = "",
) -> RuleOverrideDraft:
    """Build the typed boundary from flat browser form fields."""

    return RuleOverrideDraft(
        face=FACE,
        rule_id=rule_id,
        family=family,
        description=description,
        message_key=message_key,
        severity=severity,
        emits_signal=emits_signal or None,
        disabled=disabled,
        patterns={
            "uz_latn": _split_patterns(patterns_uz_latn),
            "uz_cyrl": _split_patterns(patterns_uz_cyrl),
            "ru": _split_patterns(patterns_ru),
        },
    )


def _split_patterns(raw: str) -> list[str]:
    """One pattern per line; blank lines are ignored rather than rejected."""

    return [line.strip() for line in raw.splitlines() if line.strip()]


@router.get("/admin/rules", response_class=HTMLResponse, include_in_schema=False)
async def admin_rules(request: Request, language: str = DEFAULT_LANGUAGE) -> Response:
    """List every override alongside the baseline pack size."""

    settings = _admin_settings(request)
    language = _normalize_language(language)
    redirect = _require_admin(request, settings, language)
    if redirect is not None:
        return redirect

    session_factory = _session_factory_or_error(request)
    async with session_factory() as session:
        overrides = await list_overrides(session, face=FACE)
    return _no_store(
        templates.TemplateResponse(
            request,
            "admin_rules.html",
            _context(
                request,
                language,
                overrides=overrides,
                baseline_count=len(load_yaml_rule_pack(FACE).rules),
                active_count=len(load_rule_pack(FACE).rules),
            ),
        )
    )


@router.get("/admin/rules/new", response_class=HTMLResponse, include_in_schema=False)
async def admin_rule_new(request: Request, language: str = DEFAULT_LANGUAGE) -> Response:
    """Render an empty rule editor."""

    settings = _admin_settings(request)
    language = _normalize_language(language)
    redirect = _require_admin(request, settings, language)
    if redirect is not None:
        return redirect
    return _form_response(request, language, override=None)


@router.get(
    "/admin/rules/{override_id}/edit",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def admin_rule_edit(
    request: Request,
    override_id: uuid.UUID,
    language: str = DEFAULT_LANGUAGE,
) -> Response:
    """Render an existing override in the editor."""

    settings = _admin_settings(request)
    language = _normalize_language(language)
    redirect = _require_admin(request, settings, language)
    if redirect is not None:
        return redirect
    session_factory = _session_factory_or_error(request)
    async with session_factory() as session:
        override = await get_override(session, override_id)
    if override is None:
        raise HTTPException(status_code=404)
    return _form_response(request, language, override=override)


@router.post("/admin/rules/preview", response_class=HTMLResponse, include_in_schema=False)
async def admin_rule_preview(
    request: Request,
    draft: Annotated[RuleOverrideDraft, Depends(_draft_from_form)],
    sample: Annotated[str, Form()] = "",
    override_id: Annotated[str, Form()] = "",
    language: Annotated[str, Form()] = DEFAULT_LANGUAGE,
) -> Response:
    """Dry-run the edited rule against sample text without saving anything."""

    require_same_origin(request)
    settings = _admin_settings(request)
    language = _normalize_language(language)
    redirect = _require_admin(request, settings, language)
    if redirect is not None:
        return redirect

    matched: tuple[str, ...] = ()
    error: str | None = None
    try:
        matched = preview_rule(draft, sample)
    except ValueError as exc:
        error = _error_text(language, str(exc))

    return _form_response(
        request,
        language,
        override=draft,
        override_id=override_id or None,
        error=error,
        sample=sample,
        # Distinguish "ran and matched nothing" from "never ran".
        preview_ran=error is None and bool(sample.strip()),
        matched=matched,
    )


@router.post("/admin/rules", response_class=HTMLResponse, include_in_schema=False)
async def admin_rule_save(
    request: Request,
    draft: Annotated[RuleOverrideDraft, Depends(_draft_from_form)],
    override_id: Annotated[str, Form()] = "",
    sample: Annotated[str, Form()] = "",
    language: Annotated[str, Form()] = DEFAULT_LANGUAGE,
) -> Response:
    """Create or update one override, then republish the merged pack."""

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
                existing = await get_override(session, uuid.UUID(override_id))
                if existing is None:
                    raise HTTPException(status_code=404)
                await update_override(session, existing, draft)
            else:
                await create_override(session, draft)
            await session.commit()
            # Republish immediately: waiting out the refresh interval would
            # leave the operator unable to tell whether the edit took effect.
            await refresh_rule_pack(session, FACE)
    except IntegrityError:
        error = _error_text(language, "duplicate_rule")
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
    return _no_store(RedirectResponse(f"/admin/rules?language={language}", status_code=303))


@router.post("/admin/rules/{override_id}/delete", include_in_schema=False)
async def admin_rule_delete(
    request: Request,
    override_id: uuid.UUID,
    language: Annotated[str, Form()] = DEFAULT_LANGUAGE,
) -> Response:
    """Delete an override so the shipped baseline rule applies again."""

    require_same_origin(request)
    settings = _admin_settings(request)
    language = _normalize_language(language)
    redirect = _require_admin(request, settings, language)
    if redirect is not None:
        return redirect

    session_factory = _session_factory_or_error(request)
    async with session_factory() as session:
        override = await get_override(session, override_id)
        if override is None:
            raise HTTPException(status_code=404)
        await delete_override(session, override)
        await session.commit()
        await refresh_rule_pack(session, FACE)
    return _no_store(RedirectResponse(f"/admin/rules?language={language}", status_code=303))


def _form_response(
    request: Request,
    language: str,
    *,
    override: RuleOverride | RuleOverrideDraft | None,
    override_id: str | None = None,
    error: str | None = None,
    sample: str = "",
    preview_ran: bool = False,
    matched: tuple[str, ...] = (),
    status_code: int = 200,
) -> HTMLResponse:
    resolved_id = override_id or (
        str(override.id) if isinstance(override, RuleOverride) else None
    )
    return _no_store(
        templates.TemplateResponse(
            request,
            "admin_rule_form.html",
            _context(
                request,
                language,
                override=override,
                override_id=resolved_id,
                patterns=_patterns_for_form(override),
                pattern_languages=PATTERN_LANGUAGES,
                error=error,
                sample=sample,
                preview_ran=preview_ran,
                matched=matched,
            ),
            status_code=status_code,
        )
    )


def _patterns_for_form(
    override: RuleOverride | RuleOverrideDraft | None,
) -> dict[str, str]:
    """Render stored patterns back into one-per-line textarea values."""

    stored = getattr(override, "patterns", None) or {}
    return {
        language: "\n".join(stored.get(language, []) or []) for language in PATTERN_LANGUAGES
    }


def _error_text(language: str, key: str) -> str:
    errors = RULES_COPY[language]["errors"]
    return errors.get(key, errors["invalid_patterns"])


def _context(request: Request, language: str, **extra) -> dict:
    return {
        "request": request,
        "copy": WEB_COPY[language],
        "editorial": EDITORIAL_COPY[language],
        "rules": RULES_COPY[language],
        "language": language,
        "languages": LANGUAGES,
        "language_labels": LANGUAGE_LABELS,
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
    request: Request, settings: Settings, language: str
) -> RedirectResponse | None:
    if is_admin_authenticated(request, settings):
        return None
    return _no_store(RedirectResponse(f"/admin/login?language={language}", status_code=303))


def _session_factory_or_error(request: Request) -> async_sessionmaker[AsyncSession]:
    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory is None:
        raise HTTPException(status_code=503, detail="Rule storage is not configured.")
    return session_factory


def _normalize_language(language: str) -> str:
    return language if language in LANGUAGES else DEFAULT_LANGUAGE


def _no_store(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response
