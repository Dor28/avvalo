"""Shared test fixtures.

By default unit tests run against an in-memory SQLite database (the spec permits
SQLite for local unit tests only). A ``StaticPool`` keeps the single in-memory
connection alive for the life of the session so the schema persists across calls.

Setting ``TEST_DATABASE_URL`` to a Postgres DSN runs the same fixtures against a
real Postgres instead. CI does this so the production column types are actually
exercised: ``rule_ids``, ``knowledge_card_ids``, and ``reviewed_case_ids`` are
``ARRAY(Text)`` on Postgres and fall back to ``JSON`` on SQLite (see
``RULE_IDS_TYPE`` in ``app/data/models.py``), so the shipped type never runs
under the default SQLite suite.

Against Postgres the schema is created once and each test runs inside a
transaction that is rolled back afterwards. A test's own ``commit()`` lands on a
savepoint, so per-test isolation holds without paying for a schema rebuild each
time.
"""

import json
import os
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool, StaticPool

from app.data.models import Base

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_DIR = REPO_ROOT / "tests" / "fixtures" / "golden"

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "").strip()


# The Postgres schema is built once per test process. Each test still gets its
# own engine, because pytest-asyncio gives every test a fresh event loop and an
# asyncpg pool cannot be shared across loops.
_postgres_schema_ready = False


async def _postgres_session():
    """Yield a session isolated by a transaction that is rolled back afterwards."""

    global _postgres_schema_ready

    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    try:
        if not _postgres_schema_ready:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
                await conn.run_sync(Base.metadata.create_all)
            _postgres_schema_ready = True

        connection = await engine.connect()
        transaction = await connection.begin()
        db_session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            yield db_session
        finally:
            await db_session.close()
            if transaction.is_active:
                await transaction.rollback()
            await connection.close()
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def session():
    """Yield an :class:`AsyncSession` bound to a clean database."""

    if TEST_DATABASE_URL:
        async for db_session in _postgres_session():
            yield db_session
        return

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
