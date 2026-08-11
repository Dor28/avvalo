"""Operator-only editor for the rule overrides layered onto the shipped pack.

Editing detection patterns through a form is safety-critical: a bad pattern
degrades detection silently for every user, and this box deploys from ``main``.
Every route therefore forces a dry-run affordance and republishes the merged
pack immediately on save, so an operator sees the real effect rather than
waiting out the refresh interval.

The list shows the shipped baseline rules alongside the stored overrides. An
override-only list renders an empty page on a fresh database while the baseline
rules are matching real content, which makes the rules in force impossible to
review and their IDs impossible to discover.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.texts import DEFAULT_LANGUAGE, LANGUAGE_LABELS, LANGUAGES
from app.config import Settings
from app.engine.rules.loader import RuleDefinition, load_rule_pack, load_yaml_rule_pack
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
from app.web.copy import WEB_COPY
from app.web.editorial_copy import EDITORIAL_COPY
from app.web.knowledge_copy import KNOWLEDGE_COPY
from app.web.routes import templates
from app.web.rules_copy import (
    FAMILY_PRESENTATION,
    MESSAGE_LABELS,
    RULES_COPY,
    SCRIPT_LABELS,
    SEVERITY_PRESENTATION,
)

router = APIRouter()


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

    # This key is fallback metadata rather than an editorial decision. The
    # stable final segment of the required rule ID is a sufficient default.
    resolved_message_key = message_key or rule_id.rsplit(".", maxsplit=1)[-1]

    return RuleOverrideDraft(
        rule_id=rule_id,
        family=family,
        description=description,
        message_key=resolved_message_key,
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


@dataclass(frozen=True)
class _RuleRow:
    """One list row: a stored override, or a shipped rule with no override yet."""

    rule_id: str
    family: str
    family_label: str
    title: str
    summary: str
    description: str
    severity: int
    severity_label: str
    disabled: bool
    edit_url: str
    override_id: str | None
    updated_ts: datetime | None

    @property
    def is_baseline(self) -> bool:
        return self.override_id is None


def _draft_from_rule(rule: RuleDefinition) -> RuleOverrideDraft:
    """Project a shipped baseline rule onto the editor's draft contract.

    Editing a baseline rule opens this draft with no ``override_id``, so saving
    creates an override carrying the same ID — which is exactly how the merge in
    ``app.rules_store.apply`` replaces a baseline rule.
    """

    return RuleOverrideDraft(
        rule_id=rule.id,
        family=rule.family,
        description=rule.desc,
        message_key=rule.message_key,
        severity=rule.severity,
        emits_signal=rule.emits_signal,
        patterns={
            language: list(rule.match.get(language, ())) for language in PATTERN_LANGUAGES
        },
        disabled=False,
    )


def _rule_rows(
    overrides: list[RuleOverride],
    baseline: tuple[RuleDefinition, ...],
    language: str,
) -> list[_RuleRow]:
    """Overrides newest-first, then the baseline rules no override replaces."""

    overridden = {override.rule_id for override in overrides}
    rows = [
        _rule_row(
            rule_id=override.rule_id,
            family=override.family,
            message_key=override.message_key,
            description=override.description,
            severity=override.severity,
            disabled=override.disabled,
            edit_url=f"/admin/rules/{override.id}/edit?language={language}",
            override_id=str(override.id),
            updated_ts=override.updated_ts,
            language=language,
        )
        for override in overrides
    ]
    rows.extend(
        _rule_row(
            rule_id=rule.id,
            family=rule.family,
            message_key=rule.message_key,
            description=rule.desc,
            severity=rule.severity,
            disabled=False,
            edit_url=f"/admin/rules/baseline/{rule.id}/edit?language={language}",
            override_id=None,
            updated_ts=None,
            language=language,
        )
        for rule in sorted(baseline, key=lambda rule: rule.id)
        if rule.id not in overridden
    )
    return rows


def _rule_row(
    *,
    rule_id: str,
    family: str,
    message_key: str,
    description: str,
    severity: int,
    disabled: bool,
    edit_url: str,
    override_id: str | None,
    updated_ts: datetime | None,
    language: str,
) -> _RuleRow:
    """Add localized presentation without altering any stored rule value."""

    family_copy = FAMILY_PRESENTATION[language].get(family)
    family_label = family_copy["label"] if family_copy else _humanize_key(family)
    summary = family_copy["summary"] if family_copy else description
    title = MESSAGE_LABELS[language].get(message_key, family_label)
    severity_copy = SEVERITY_PRESENTATION[language].get(severity)
    severity_label = severity_copy["label"] if severity_copy else str(severity)
    return _RuleRow(
        rule_id=rule_id,
        family=family,
        family_label=family_label,
        title=title,
        summary=summary,
        description=description,
        severity=severity,
        severity_label=severity_label,
        disabled=disabled,
        edit_url=edit_url,
        override_id=override_id,
        updated_ts=updated_ts,
    )


def _humanize_key(value: str) -> str:
    """Readable fallback for custom taxonomy keys not known by this release."""

    return value.replace("_", " ").strip().capitalize()


@router.get("/admin/rules", response_class=HTMLResponse, include_in_schema=False)
async def admin_rules(request: Request, language: str = DEFAULT_LANGUAGE) -> Response:
    """List the stored overrides and the shipped rules none of them replaces."""

    settings = _admin_settings(request)
    language = _normalize_language(language)
    redirect = _require_admin(request, settings, language)
    if redirect is not None:
        return redirect

    session_factory = _session_factory_or_error(request)
    async with session_factory() as session:
        overrides = await list_overrides(session)
    baseline = load_yaml_rule_pack().rules
    return _no_store(
        templates.TemplateResponse(
            request,
            "admin_rules.html",
            _context(
                request,
                language,
                rows=_rule_rows(overrides, baseline, language),
                baseline_count=len(baseline),
                active_count=len(load_rule_pack().rules),
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
    "/admin/rules/baseline/{rule_id}/edit",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def admin_rule_baseline_edit(
    request: Request,
    rule_id: str,
    language: str = DEFAULT_LANGUAGE,
) -> Response:
    """Open a shipped rule pre-filled; saving stores an override with its ID."""

    settings = _admin_settings(request)
    language = _normalize_language(language)
    redirect = _require_admin(request, settings, language)
    if redirect is not None:
        return redirect
    rule = next(
        (rule for rule in load_yaml_rule_pack().rules if rule.id == rule_id),
        None,
    )
    if rule is None:
        raise HTTPException(status_code=404)
    return _form_response(request, language, override=_draft_from_rule(rule))


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
            await refresh_rule_pack(session)
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
        await refresh_rule_pack(session)
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
                family_options=_family_options(language, override),
                severity_options=SEVERITY_PRESENTATION[language],
                error=error,
                sample=sample,
                preview_ran=preview_ran,
                matched=matched,
            ),
            status_code=status_code,
        )
    )


def _family_options(
    language: str,
    override: RuleOverride | RuleOverrideDraft | None,
) -> list[tuple[str, dict[str, str]]]:
    """Known taxonomy choices plus an existing custom value, if necessary."""

    options = list(FAMILY_PRESENTATION[language].items())
    current = getattr(override, "family", None)
    if current and current not in FAMILY_PRESENTATION[language]:
        options.append(
            (
                current,
                {
                    "label": _humanize_key(current),
                    "summary": getattr(override, "description", ""),
                },
            )
        )
    return options


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
        raise HTTPException(status_code=503, detail="Rule storage is not configured.")
    return session_factory


def _normalize_language(language: str) -> str:
    return language if language in LANGUAGES else DEFAULT_LANGUAGE


def _no_store(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response
