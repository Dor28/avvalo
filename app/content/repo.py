"""Validated persistence for founder-authored editorial case posts."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.content.models import EditorialPost

CATEGORIES = ("payments", "phishing", "marketplace", "jobs", "accounts", "documents")
STATES = {"draft", "published"}
LANGUAGES = {"uz_latn", "uz_cyrl", "ru"}
SLUG_MAX_CHARS = 100
TITLE_MAX_CHARS = 160
SUMMARY_MAX_CHARS = 320
ARTICLE_MAX_CHARS = 12_000
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class EditorialPostDraft(BaseModel):
    """Validated values accepted from the founder-only editor."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    slug: str
    category: str
    state: str
    title_uz_latn: str
    summary_uz_latn: str
    article_uz_latn: str
    title_uz_cyrl: str
    summary_uz_cyrl: str
    article_uz_cyrl: str
    title_ru: str
    summary_ru: str
    article_ru: str

    def normalized(self) -> EditorialPostDraft:
        """Strip surrounding whitespace and reject unsupported or oversized values."""

        values = {field: str(getattr(self, field)).strip() for field in type(self).model_fields}
        slug = values["slug"].casefold()
        if not slug or len(slug) > SLUG_MAX_CHARS or not SLUG_RE.fullmatch(slug):
            raise ValueError("invalid_slug")
        if values["category"] not in CATEGORIES:
            raise ValueError("invalid_category")
        if values["state"] not in STATES:
            raise ValueError("invalid_state")

        for language in LANGUAGES:
            _validate_required(values[f"title_{language}"], TITLE_MAX_CHARS, "invalid_title")
            _validate_required(
                values[f"summary_{language}"], SUMMARY_MAX_CHARS, "invalid_summary"
            )
            _validate_required(
                values[f"article_{language}"], ARTICLE_MAX_CHARS, "invalid_article"
            )
        values["slug"] = slug
        return EditorialPostDraft(**values)


@dataclass(frozen=True)
class LocalizedEditorialPost:
    """Public projection containing one language and no admin-only draft fields."""

    id: uuid.UUID
    slug: str
    category: str
    title: str
    summary: str
    article: str
    published_ts: datetime

    @property
    def reading_minutes(self) -> int:
        """Return a small deterministic reading-time hint."""

        return max(1, round(len(self.article.split()) / 180))


async def create_post(session: AsyncSession, draft: EditorialPostDraft) -> EditorialPost:
    """Create a new draft or published article and flush it."""

    values = draft.normalized()
    now = datetime.now(UTC)
    post = EditorialPost(
        id=uuid.uuid4(),
        **values.__dict__,
        created_ts=now,
        updated_ts=now,
        published_ts=now if values.state == "published" else None,
    )
    session.add(post)
    await session.flush()
    return post


async def update_post(
    session: AsyncSession,
    post: EditorialPost,
    draft: EditorialPostDraft,
) -> EditorialPost:
    """Replace editable values while preserving creation and first-publish times."""

    values = draft.normalized()
    for field, value in values.__dict__.items():
        setattr(post, field, value)
    now = datetime.now(UTC)
    post.updated_ts = now
    if values.state == "published" and post.published_ts is None:
        post.published_ts = now
    await session.flush()
    return post


async def get_admin_post(session: AsyncSession, post_id: uuid.UUID) -> EditorialPost | None:
    """Return one article regardless of publication state."""

    return await session.get(EditorialPost, post_id)


async def list_admin_posts(session: AsyncSession) -> list[EditorialPost]:
    """Return all articles for the editorial dashboard."""

    result = await session.execute(
        select(EditorialPost).order_by(EditorialPost.updated_ts.desc())
    )
    return list(result.scalars())


async def list_published_posts(
    session: AsyncSession,
    *,
    language: str,
    limit: int | None = None,
) -> list[LocalizedEditorialPost]:
    """Return published posts newest-first in the requested supported language."""

    language = language if language in LANGUAGES else "ru"
    statement = (
        select(EditorialPost)
        .where(
            EditorialPost.state == "published",
            EditorialPost.published_ts.is_not(None),
        )
        .order_by(EditorialPost.published_ts.desc())
    )
    if limit is not None:
        statement = statement.limit(limit)
    rows = (await session.execute(statement)).scalars()
    return [_localized(post, language) for post in rows]


async def get_published_post(
    session: AsyncSession,
    *,
    slug: str,
    language: str,
) -> LocalizedEditorialPost | None:
    """Return a published article by slug, never exposing drafts."""

    post = (
        await session.execute(
            select(EditorialPost).where(
                EditorialPost.slug == slug,
                EditorialPost.state == "published",
                EditorialPost.published_ts.is_not(None),
            )
        )
    ).scalar_one_or_none()
    return _localized(post, language if language in LANGUAGES else "ru") if post else None


def _localized(post: EditorialPost, language: str) -> LocalizedEditorialPost:
    published_ts = post.published_ts
    if published_ts is None:
        raise ValueError("published post has no publication timestamp")
    return LocalizedEditorialPost(
        id=post.id,
        slug=post.slug,
        category=post.category,
        title=getattr(post, f"title_{language}"),
        summary=getattr(post, f"summary_{language}"),
        article=getattr(post, f"article_{language}"),
        published_ts=published_ts,
    )


def _validate_required(value: str, maximum: int, error: str) -> None:
    if not value or len(value) > maximum:
        raise ValueError(error)
