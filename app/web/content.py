"""Markdown content loading for the public scam education pages."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache, lru_cache
from pathlib import Path
from typing import Any

import markdown
import yaml

DEFAULT_LANGUAGE = "uz_latn"
CONTENT_ROOT = Path(__file__).resolve().parents[2] / "content" / "scams"
RULE_PACK_PATH = Path(__file__).resolve().parents[2] / "rules" / "family" / "families.yaml"
LANGUAGE_ORDER = ("uz_latn", "uz_cyrl", "ru")


@dataclass(frozen=True)
class ScamArticle:
    """Rendered scam education article loaded from markdown."""

    slug: str
    language: str
    requested_language: str
    title: str
    description: str
    published: bool
    html: str
    source_path: Path

    @property
    def is_fallback(self) -> bool:
        return self.language != self.requested_language


@cache
def scam_slugs() -> tuple[str, ...]:
    """Return family slugs derived from the family rule pack."""

    data = yaml.safe_load(RULE_PACK_PATH.read_text(encoding="utf-8")) or {}
    return tuple(str(item["family"]) for item in data.get("families", []) if item.get("family"))


def available_languages(slug: str) -> tuple[str, ...]:
    """Return languages that have a markdown file for *slug*."""

    languages = [
        language
        for language in LANGUAGE_ORDER
        if _article_path(slug, language).exists()
    ]
    return tuple(languages)


def get_article(
    slug: str, language: str, *, include_drafts: bool = False
) -> ScamArticle | None:
    """Return one article in the requested language, falling back when needed."""

    if slug not in scam_slugs():
        return None

    requested_language = language if language in LANGUAGE_ORDER else DEFAULT_LANGUAGE
    candidates = _candidate_languages(slug, requested_language)
    for candidate in candidates:
        path = _article_path(slug, candidate)
        if not path.exists():
            continue
        article = _load_article(str(path), path.stat().st_mtime_ns, slug, candidate)
        if article.published or include_drafts:
            return ScamArticle(
                slug=article.slug,
                language=article.language,
                requested_language=requested_language,
                title=article.title,
                description=article.description,
                published=article.published,
                html=article.html,
                source_path=article.source_path,
            )
    return None


def list_articles(language: str, *, include_drafts: bool = False) -> list[ScamArticle]:
    """Return visible scam articles in rule-pack order."""

    articles = [
        article
        for slug in scam_slugs()
        if (article := get_article(slug, language, include_drafts=include_drafts))
    ]
    return articles


def sitemap_articles() -> list[ScamArticle]:
    """Return all published localized scam pages."""

    articles: list[ScamArticle] = []
    for slug in scam_slugs():
        for language in available_languages(slug):
            path = _article_path(slug, language)
            article = _load_article(str(path), path.stat().st_mtime_ns, slug, language)
            if article.published:
                articles.append(
                    ScamArticle(
                        slug=article.slug,
                        language=article.language,
                        requested_language=article.language,
                        title=article.title,
                        description=article.description,
                        published=article.published,
                        html=article.html,
                        source_path=article.source_path,
                    )
                )
    return articles


def _candidate_languages(slug: str, language: str) -> tuple[str, ...]:
    candidates = [language, DEFAULT_LANGUAGE, *available_languages(slug)]
    deduped: list[str] = []
    for candidate in candidates:
        if candidate not in deduped:
            deduped.append(candidate)
    return tuple(deduped)


def _article_path(slug: str, language: str) -> Path:
    return CONTENT_ROOT / language / f"{slug}.md"


@lru_cache(maxsize=256)
def _load_article(path_str: str, _mtime_ns: int, slug: str, language: str) -> ScamArticle:
    path = Path(path_str)
    front_matter, body = _parse_markdown(path.read_text(encoding="utf-8"))
    return ScamArticle(
        slug=slug,
        language=language,
        requested_language=language,
        title=str(front_matter.get("title", slug.replace("_", " ").title())),
        description=str(front_matter.get("description", "")),
        published=bool(front_matter.get("published", False)),
        html=markdown.markdown(body, extensions=["extra"]),
        source_path=path,
    )


def _parse_markdown(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    _, rest = text.split("---\n", 1)
    raw_front_matter, body = rest.split("\n---\n", 1)
    front_matter = yaml.safe_load(raw_front_matter) or {}
    return front_matter, body.lstrip()
