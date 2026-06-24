"""Shared test fixtures.

Unit tests run against an in-memory SQLite database (the spec permits SQLite for
local unit tests only). A ``StaticPool`` keeps the single in-memory connection
alive for the life of the session so the schema persists across calls.
"""

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.data.models import Base


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
