"""Shared test fixtures.

Unit tests run against an in-memory SQLite database (the spec permits SQLite for
local unit tests only). A ``StaticPool`` keeps the single in-memory connection
alive for the life of the session so the schema persists across calls.
"""

import json
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.data.models import Base

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_DIR = REPO_ROOT / "tests" / "fixtures" / "golden"


@pytest_asyncio.fixture
async def session():
    """Yield an :class:`AsyncSession` bound to a fresh in-memory database."""

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db_session:
        yield db_session

    await engine.dispose()


@pytest.fixture
def golden():
    """Return a loader for the end-to-end golden fixtures (``golden()``)."""

    def _load(name: str = "checks") -> list[dict]:
        return json.loads((GOLDEN_DIR / f"{name}.json").read_text(encoding="utf-8"))

    return _load


@pytest.fixture
def callable_or_skip():
    """Import a module and return the first named callable, else skip the test.

    Lets the not-yet-built tasks (T6-T13) ship as live acceptance specs: each
    skips cleanly until its module lands, then runs for real.
    """

    def _get(module_path: str, *names: str):
        module = pytest.importorskip(module_path)
        for name in names:
            candidate = getattr(module, name, None)
            if callable(candidate):
                return candidate
        pytest.skip(f"{module_path}: none of {names} implemented yet")

    return _get
