"""Async SQLAlchemy engine helpers."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_database_engine(database_url: str) -> AsyncEngine:
    """Create the shared async database engine."""

    return create_async_engine(database_url, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Return an async session factory bound to *engine* (caller owns the transaction)."""

    return async_sessionmaker(engine, expire_on_commit=False)


async def check_database_connection(engine: AsyncEngine) -> None:
    """Fail process startup unless the configured database accepts a connection."""

    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
